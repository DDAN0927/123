#!/bin/bash
# 启动脚本（容器 / 沙箱 / 本地都能用）
#
# 两种模式，自动判断：
#   A. 双进程（有 server.jar 且有 java）：SpringBoot 占 $PORT 对外，Python 只在 127.0.0.1:$AI_PORT
#   B. 单进程（没有 java 或 jar）：Python 直接对外，行为与旧版完全一致
#
# 为什么要有 B：沙箱发布（deploy/）可能装不上 JRE（下载失败 / 平台限制），
# 那时至少要保证「AI 对话还能用」，而不是整站起不来。脚本在两种环境里跑同一份，
# 少一个分支判断就会让「本地能起、线上起不来」这种问题重新出现。
# 注意 B 模式下登录/行程/记账是**不可用**的（那些接口只存在于 SpringBoot），
# 所以 deploy/ 现在会带上 server.jar，并在 install.sh 里解一个 JRE 出来。
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

PORT="${PORT:-7860}"
AI_PORT="${AI_PORT:-7861}"
export DATA_DIR="${DATA_DIR:-/mnt/workspace/data}"
export KB_DIR="${KB_DIR:-/mnt/workspace/knowledge_base}"

mkdir -p "$DATA_DIR" "$KB_DIR" 2>/dev/null || true

# 启动阶段标记：写进**持久化卷**，跨部署保留。
#
# 为什么需要：部署平台在启动失败时只回一句「starting studio failed」，不提供
# 任何日志接口（/logs、/runtime/logs 全是 404）。容器一挂，现场就没了。
# 把「走到哪一步、耗时多少」记在卷上，下一次启动（或退回单进程后）就能通过
# /health 的 boot_tail 看到上一次死在哪 —— 这是唯一能在平台外拿到现场的办法。
BOOT_LOG="$DATA_DIR/boot.log"
boot() {
  printf '%s %s\n' "$(date +%H:%M:%S)" "$*" >>"$BOOT_LOG" 2>/dev/null || true
}
boot "==== 启动 pid=$$ port=$PORT ai_port=$AI_PORT data=$DATA_DIR kb=$KB_DIR"

# 把 .env 导进环境。
# 为什么需要：.env 原本只有 Python 侧会自己读（pydantic-settings 直接解析文件），
# SpringBoot 只认环境变量。Docker/魔搭有编排层注入，沙箱没有 —— 于是管理员密码
# 会静默退回默认的 admin123、ALLOW_REGISTRATION 被忽略。都是不报错的错。
# 已存在的环境变量优先（编排层 / 平台注入的值不该被文件覆盖）。
if [ -f .env ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in ''|'#'*) continue ;; esac
    key="${line%%=*}"
    val="${line#*=}"
    case "$key" in ''|*[!A-Za-z0-9_]*) continue ;; esac
    [ -n "${!key:-}" ] || export "$key=$val"
  done < .env
fi

# 把镜像内置攻略同步到持久化目录：**按内容比较**，不同才覆盖。
# 为什么不用 cp -n：已存在就跳过，会让镜像里的攻略更新永远进不了持久化卷 ——
#   卷上还是上一版正文，本地测试一切正常、线上一直答旧内容，极难发现。
# 为什么不用 cp -u：它比 mtime，而镜像层与卷的时钟来源不同，判不准。
# 管理员另存的文档名与内置的不同，不会被这段逻辑碰到。
for f in knowledge_base/*.md; do
  [ -e "$f" ] || continue
  dest="$KB_DIR/$(basename "$f")"
  if [ ! -f "$dest" ] || ! cmp -s "$f" "$dest"; then
    cp "$f" "$dest"
  fi
done

# 子目录档位（导览档 guides/、清单档 spots/）用**镜像**语义而不是叠加：
# 这两档完全由脚本从维基导游 / 地图数据推导，镜像里删掉的城市在卷上也不该留着，
# 否则重建索引后还会检到已经不存在的城市。只清这两个子目录，不碰根目录的管理员文档。
#
# 为什么抽成函数：新增档位时最容易漏的就是这里 —— 只加了生成脚本、忘了同步，
# 文件在镜像里躺着却永远进不了 $KB_DIR，线上 guided_count 一直是 0，
# 而且没有任何报错（索引照常构建，只是少了一档）。
sync_tier() {
  local sub="$1"
  [ -d "knowledge_base/$sub" ] || return 0
  mkdir -p "$KB_DIR/$sub"
  for f in knowledge_base/"$sub"/*.md; do
    [ -e "$f" ] || continue
    dest="$KB_DIR/$sub/$(basename "$f")"
    if [ ! -f "$dest" ] || ! cmp -s "$f" "$dest"; then
      cp "$f" "$dest"
    fi
  done
  for f in "$KB_DIR/$sub"/*.md; do
    [ -e "$f" ] || continue
    [ -f "knowledge_base/$sub/$(basename "$f")" ] || rm -f "$f"
  done
}
sync_tier guides
sync_tier spots
boot "知识库已同步 root=$(ls "$KB_DIR"/*.md 2>/dev/null | wc -l) guides=$(ls "$KB_DIR"/guides/*.md 2>/dev/null | wc -l) spots=$(ls "$KB_DIR"/spots/*.md 2>/dev/null | wc -l)"

# 预构建索引：发布包里带了一份（scripts/build_kb.py 的产物），装进持久化卷。
#
# 为什么必须有这一步：索引重建是**同步**跑在 lifespan 里的，建完才 bind 端口。
# 1042 块在 1~2 核容器上要 1~2 分钟 —— 魔搭那边靠 420 秒等待能兜住，沙箱发布
# 只等 60 秒，直接判「服务没有在指定端口上响应」，而真实原因只是「还没建完」。
# 包里带索引 + 索引签名按内容比对（见 app/rag/indexer.doc_signature），冷启动
# 就能跳过重建，端口几秒内就起来。
#
# 幂等标记用「包内索引的指纹」而不是时间戳：同一份包重复启动不覆盖运行时重建的
# 结果 —— 管理员上传过文档时，卷上那份索引才是对的（它比包里的新）。
if [ -f data/index/faiss.index ] && [ -f data/index/meta.json ]; then
  shipped="$(cat data/index/faiss.index data/index/meta.json 2>/dev/null | cksum | cut -d' ' -f1)"
  marker="$DATA_DIR/index/.shipped"
  if [ "$(cat "$marker" 2>/dev/null)" != "$shipped" ]; then
    mkdir -p "$DATA_DIR/index"
    cp -f data/index/* "$DATA_DIR/index/" 2>/dev/null || true
    printf '%s' "$shipped" >"$marker"
    echo "[start] 已装入预构建索引（跳过冷启动重建）"
    boot "预构建索引已装入 $DATA_DIR/index"
  fi
fi

# ---------- 解释器 ----------
if [ -n "${PYTHON_BIN:-}" ]; then
  PY="$PYTHON_BIN"
elif command -v python >/dev/null 2>&1; then
  PY=python
elif [ -x .venv/Scripts/python.exe ]; then
  PY=.venv/Scripts/python.exe
elif [ -x .venv/bin/python ]; then
  PY=.venv/bin/python
else
  PY=python3
fi

# 诊断开关：强制只跑 Python（不启动 SpringBoot、不等 AI 就绪）。
#
# 用在「部署平台判定启动失败、但拿不到日志」的时候：把两段等待全部绕开，
# 让端口第一时间暴露出来，这样至少能读到 /health 与 $DATA_DIR/boot.log，
# 判断到底是 Python 侧起不来，还是卡在等 AI 就绪 / SpringBoot 那两段。
# 正常情况下不要开 —— 单进程模式没有登录、行程、记账。
if [ -n "${SINGLE_PROCESS:-}" ]; then
  echo "[start] SINGLE_PROCESS=1 → 强制单进程（诊断用，无登录/行程）"
  boot "强制单进程（SINGLE_PROCESS=1）"
  exec "$PY" -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
fi

# ---------- 有没有 Java 侧 ----------
JAR="${JAR_PATH:-$SCRIPT_DIR/server.jar}"
JAVA_BIN=""
if [ -f "$JAR" ]; then
  # 依次找：JAVA_HOME → 沙箱里 install.sh 解的 ./jre → PATH 上的 java。
  # ./jre 这一项是沙箱专用的：pyenv 基础镜像装不了 JDK，也没有全局 PATH。
  # 每个候选都试 `java` 和 `java.exe`：Windows 上可执行文件带后缀，[ -x .../java ] 恒假。
  for cand in "${JAVA_HOME:+$JAVA_HOME/bin/java}" "$SCRIPT_DIR/jre/bin/java" "$(command -v java 2>/dev/null || true)"; do
    [ -n "$cand" ] || continue
    if [ -x "$cand" ]; then
      JAVA_BIN="$cand"
      break
    elif [ -x "$cand.exe" ]; then
      JAVA_BIN="$cand.exe"
      break
    fi
  done
fi

# 单进程模式：Python 直接对外
if [ -z "$JAVA_BIN" ]; then
  echo "[start] 未找到 server.jar 或 java → 单进程模式（仅 AI 服务对外，端口 $PORT）"
  boot "单进程模式（无 jar/java），直接对外 :$PORT"
  exec "$PY" -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
fi

# ---------- 双进程模式 ----------
# 两个密钥都放持久化卷：每次重启重新生成的话，所有已登录用户会被踢下线
# （JWT 签名变了），而且 SpringBoot 与 Python 的内部密钥不一致会直接 403。
read_or_make_secret() {
  local file="$1" bytes="${2:-32}"
  if [ -s "$file" ]; then
    cat "$file"
    return
  fi
  local value
  value="$(head -c "$bytes" /dev/urandom | base64 | tr -d '\n=+/' | cut -c1-43)"
  printf '%s' "$value" >"$file"
  chmod 600 "$file" 2>/dev/null || true
  printf '%s' "$value"
}

if [ -z "${AI_INTERNAL_SECRET:-}" ]; then
  AI_INTERNAL_SECRET="$(read_or_make_secret "$DATA_DIR/.ai_internal_secret" 32)"
fi
if [ -z "${JWT_SECRET:-}" ]; then
  JWT_SECRET="$(read_or_make_secret "$DATA_DIR/.jwt_secret" 48)"
fi
export AI_INTERNAL_SECRET JWT_SECRET
export AI_BASE_URL="http://127.0.0.1:$AI_PORT"

echo "[start] 双进程模式：SpringBoot 对外 :$PORT，Python AI 仅内网 :$AI_PORT"
boot "双进程模式，java=$JAVA_BIN"

# 起 AI 服务，**不等它就绪**就继续。
#
# 为什么不再等：以前这里会阻塞等 /health 200，最长 420 秒。但 AI 侧要加载 torch +
# BGE 模型，1~2 核容器上要 1~3 分钟；而 uvicorn 又要等 lifespan 跑完才 bind，
# 于是「等 AI」这段时间公网端口是完全关着的。部署平台自己的启动超时比 420 秒更短
# （实测 6 分钟），等我们等够，平台早判「starting studio failed」了 —— 而且平台
# 不提供日志，只能看到一句没有信息量的错误。
#
# 关键事实：SpringBoot 的静态页、登录、行程、记账**都不依赖 AI**，只有聊天与
# 生成行程走代理。所以公网入口没有任何理由等 AI：先把 7860 开出来，AI 慢一点
# 只影响「聊天能不能立刻用」，不影响「站点是否在线」。
"$PY" -m uvicorn app.main:app --host 127.0.0.1 --port "$AI_PORT" &
AI_PID=$!
boot "AI 服务已拉起 pid=$AI_PID"

cleanup() {
  kill "$AI_PID" 2>/dev/null || true
  [ -n "${APP_PID:-}" ] && kill "$APP_PID" 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# 立刻起 SpringBoot（对外入口），与 AI 并行启动。
# 堆不要给太大：沙箱这类小规格容器上，Java 默认会按「宿主内存」算堆，
# 加上 Python + torch 很容易被 OOM killer 干掉。640m 对演示够用。
"$JAVA_BIN" ${JAVA_OPTS:--Xms128m -Xmx640m -XX:+UseSerialGC -Dfile.encoding=UTF-8} \
  -jar "$JAR" \
  --server.port="$PORT" \
  --app.ai.base-url="$AI_BASE_URL" &
APP_PID=$!
boot "SpringBoot 已拉起 pid=$APP_PID"

# 看门狗：SpringBoot 180 秒内没接上 $PORT 就杀掉它，退回单进程。
#
# 为什么要这一步：Java 侧起不来时整站是黑的（连 AI 对话都打不开），而部署平台
# 只给一句「starting studio failed, please check the log.」——它并不提供日志。
# 本地双进程实测 SpringBoot 12 秒就 Started，180 秒足够宽容；真等不到就说明
# Java 侧出了问题，此时「AI 能用、登录/行程不可用」远好过「什么都打不开」。
# 注意探的是 **TCP 端口**而不是 /api/health：健康检查本身可能依赖数据库，
# 数据库没起来时端口却已经能连上，两者要分开判断。
app_ready=0
for _ in $(seq 1 180); do
  if ! kill -0 "$APP_PID" 2>/dev/null; then
    echo " ✗"
    echo "[start] SpringBoot 进程已退出（端口 $PORT 未就绪）"
    break
  fi
  if "$PY" - "$PORT" <<'EOF' 2>/dev/null
import socket, sys

s = socket.socket()
s.settimeout(2)
try:
    s.connect(("127.0.0.1", int(sys.argv[1])))
except Exception:
    sys.exit(1)
finally:
    s.close()
EOF
  then
    app_ready=1
    boot "SpringBoot 端口已就绪"
    break
  fi
  sleep 1
done

if [ "$app_ready" -ne 1 ]; then
  echo "[start] 退回单进程模式：仅 AI 服务对外（端口 $PORT），登录/行程不可用"
  boot "✗ SpringBoot 未就绪，回退单进程"
  kill "$APP_PID" 2>/dev/null || true
  # 不能直接 `wait`：Java 侧如果卡在原生调用里，SIGTERM 不一定让它退出，
  # wait 会一直阻塞，回退逻辑永远轮不到执行 —— 那就又变成「容器活着但端口不开」。
  for _ in $(seq 1 10); do
    kill -0 "$APP_PID" 2>/dev/null || break
    sleep 1
  done
  kill -9 "$APP_PID" 2>/dev/null || true
  # 内网那个 AI 实例也要收掉：exec 会替换当前 shell，trap 里的 cleanup 不会再执行，
  # 留着它就是两个 uvicorn 各背一份 torch 模型，白吃内存。
  kill -9 "$AI_PID" 2>/dev/null || true
  exec "$PY" -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
fi

wait "$APP_PID"
