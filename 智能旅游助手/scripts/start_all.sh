#!/usr/bin/env bash
# 本地一键起两个进程（SpringBoot 对外 + Python AI 内部）
#
#   bash scripts/start_all.sh              # 默认 8080（SpringBoot）/ 7861（AI）
#   PORT=9000 bash scripts/start_all.sh    # 换对外端口
#
# 为什么需要这个脚本：两个进程必须**共享同一个内部密钥**，而且 Python 必须在
# SpringBoot 之前就绪（否则第一次点「生成行程」会拿到 502）。手工敲两条命令时
# 很容易漏掉其中一条，然后在「AI 接口 403」上排查半天。
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

# ---------- 导入 .env（与 start.sh 同一约定：已有环境变量优先） ----------
#
# 为什么必须有这段：SpringBoot 只认环境变量，不导入 .env 的话 ALLOW_REGISTRATION、
# LLM_* 等会静默落回默认值 —— 配置「没生效」零日志（实测事故：.env 写着
# ALLOW_REGISTRATION=true，用本脚本启动后注册接口照样 403，见 ux-report P2#4）。
# 注意：.env 里的 AI_INTERNAL_SECRET / JWT_SECRET 必须是非示例值 —— SecretGuard
# 会拒绝「一眼就是演示用」的默认密钥并拒绝启动，这是刻意的安全设计；换值用
#   python -c "import secrets;print(secrets.token_hex(32))"
if [ -f .env ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in ''|'#'*) continue ;; esac
    key="${line%%=*}"
    val="${line#*=}"
    case "$key" in ''|*[!A-Za-z0-9_]*) continue ;; esac
    [ -n "${!key:-}" ] || export "$key=$val"
  done < .env
fi

PORT="${PORT:-8080}"
AI_PORT="${AI_PORT:-7861}"
# 两个进程都从 $DATA_DIR 读写（SQLite / H2 / 上传图 / 密钥文件），这里统一一份
export DATA_DIR="${DATA_DIR:-./data}"
export AI_BASE_URL="http://127.0.0.1:$AI_PORT"

# ---------- 解析解释器 ----------
# 必须早于密钥生成：生成用 python 的 secrets 模块，比 /dev/urandom + base64 干净
if [ -x ".venv/Scripts/python.exe" ]; then PY=".venv/Scripts/python.exe"
elif [ -x ".venv/bin/python" ]; then PY=".venv/bin/python"
else PY="$(command -v python3 || command -v python)"; fi

# ---------- 两个密钥：没设置就生成一次并落盘复用 ----------
#
# 为什么不能再用「写死的默认值」：那等于把签名密钥公开发布 —— 任何人 clone 仓库就能
# 自签一个 role=admin 的 token。也不能每次启动重新随机：
#   1) JWT 密钥一变，所有已登录用户立刻被踢下线；
#   2) 内部密钥两侧必须**完全一致**，重新生成时若 Java 先起、Python 后起就是全站 403。
# 所以落盘到 $DATA_DIR（已 gitignore），重启复用；轮换 = 删掉对应文件再启动。
#
# 为什么不把生成结果写进 $DATA_DIR/boot.log（虽然那是最方便的排查位置）：
# Python 的 /health 会把 boot.log 末尾几行以 boot_tail 字段**公开返回**（部署平台
# 不给日志时唯一的自救手段）。把签名密钥写进去 = 把密钥挂到公网。这里只记长度与路径。
#
# ---------- 一条密钥怎么让两个进程都拿到（改这段之前务必读完）----------
#
# 唯一真源是环境变量 AI_INTERNAL_SECRET，本脚本只生成/读取一次然后 export 一次
# （见下方 `export AI_INTERNAL_SECRET JWT_SECRET`）。两个子进程都从同一个环境继承，
# 各自从自己的配置入口读到**同一个值**：
#   Python : app/config.py:78  ai_internal_secret（pydantic-settings 读同名环境变量）
#            校验在 app/api/deps.py:25 与 app/api/ai.py:35-37：
#            「请求头 X-Internal-Secret == settings.ai_internal_secret」才放行。
#   Java   : application.yml:50  internal-secret: ${AI_INTERNAL_SECRET:}
#            → AppProperties.Ai → AiProxyController:124 setHeader("X-Internal-Secret", …)
#            （AiClient:84 发给 Python 的也是同一个 props 值）
# 所以「同源」不是两边各算一次再对齐，而是**只有一个值、只生成一次**。
# 谁都不许在 Java/Python 里再补默认值或自行 random：两边一旦不一致，唯一现象就是
# 全站 403（SpringBoot 转发时带着错密钥），且日志里看不出是哪一侧错了 —— 排查成本极高。
# 手工起进程时同理：必须把同一个值同时给两个进程，否则请直接用本脚本。
read_or_make_secret() {
  local file="$1" bytes="${2:-32}"
  if [ -s "$file" ]; then
    cat "$file"
    return
  fi
  local value
  value="$("$PY" -c "import secrets;print(secrets.token_hex(${bytes}))")" || return 1
  printf '%s' "$value" >"$file"
  chmod 600 "$file" 2>/dev/null || true
  printf '%s' "$value"
}

mkdir -p "$DATA_DIR" 2>/dev/null || true
# 区分「这次新建」与「读到旧文件复用」：只按环境变量是否为空来判断，会把复用也报成
# 「生成密钥」——运维看到每次启动都"生成"密钥，会以为重启就踢掉全部登录、或两侧密钥
# 会错位，从而不敢信这个脚本。这里分别记账。
CREATED=""
REUSED=""
if [ -z "${AI_INTERNAL_SECRET:-}" ]; then
  if [ -s "$DATA_DIR/.ai_internal_secret" ]; then REUSED="${REUSED}AI_INTERNAL_SECRET "
  else CREATED="${CREATED}AI_INTERNAL_SECRET "; fi
  AI_INTERNAL_SECRET="$(read_or_make_secret "$DATA_DIR/.ai_internal_secret" 32)" || {
    echo "生成 AI_INTERNAL_SECRET 失败（python 不可用？）" >&2; exit 1; }
fi
if [ -z "${JWT_SECRET:-}" ]; then
  if [ -s "$DATA_DIR/.jwt_secret" ]; then REUSED="${REUSED}JWT_SECRET "
  else CREATED="${CREATED}JWT_SECRET "; fi
  JWT_SECRET="$(read_or_make_secret "$DATA_DIR/.jwt_secret" 32)" || {
    echo "生成 JWT_SECRET 失败（python 不可用？）" >&2; exit 1; }
fi
export AI_INTERNAL_SECRET JWT_SECRET

if [ -n "$CREATED" ]; then
  echo "[start_all] 未设置 ${CREATED}→ 已生成随机值并落盘到 $DATA_DIR（重启复用，删除文件即轮换）"
fi
if [ -n "$REUSED" ]; then
  echo "[start_all] 未设置 ${REUSED}→ 复用 $DATA_DIR 下已落盘的值（删除对应文件即轮换）"
fi

if [ -n "$CREATED$REUSED" ]; then
  # 只记「新建/复用 + 长度 + 路径」，不记明文（boot.log 会被 /health 当 boot_tail 公开读出）
  {
    if [ -n "$CREATED" ]; then
      printf '[start_all] 新建密钥：%s（长度 %s/%s，存放于 %s；删除文件即轮换）\n' \
        "$CREATED" "${#JWT_SECRET}" "${#AI_INTERNAL_SECRET}" "$DATA_DIR"
    fi
    if [ -n "$REUSED" ]; then
      printf '[start_all] 复用密钥：%s（长度 %s/%s，来自 %s）\n' \
        "$REUSED" "${#JWT_SECRET}" "${#AI_INTERNAL_SECRET}" "$DATA_DIR"
    fi
  } >>"$DATA_DIR/boot.log" 2>/dev/null || true
fi

# ---------- 解析 JDK ----------
if [ -z "${JAVA_HOME:-}" ]; then
  for cand in ".tools/jdk/jdk-17.0.2" ".tools/jdk/jdk-17"; do
    if [ -x "$cand/bin/javac" ] || [ -x "$cand/bin/javac.exe" ]; then
      JAVA_HOME="$(cd "$cand" && pwd)"; break
    fi
  done
fi
[ -n "${JAVA_HOME:-}" ] && export JAVA_HOME

JAR="server/target/travel-server.jar"
if [ ! -f "$JAR" ]; then
  echo "没找到 $JAR，先打包："
  echo "  cd server && mvn -s ../.tools/maven/settings.xml package -DskipTests"
  exit 1
fi

echo "内部密钥 : 已就绪（${#AI_INTERNAL_SECRET} 字符，不打印明文）"
echo "JWT 密钥 : 已就绪（${#JWT_SECRET} 字符）"
echo "AI 服务  : 127.0.0.1:$AI_PORT（不对外）"
echo "对外入口 : 0.0.0.0:$PORT"
# 关键配置生效值当场可见：配置「没生效」不该靠 403 才发现（ux-report P2#4）
echo "注册开关 : ALLOW_REGISTRATION=${ALLOW_REGISTRATION:-<未设置，Spring 默认 false>}"
echo "LLM     : ${LLM_BASE_URL:-<未设置，Python 侧用自身默认>}（模型 ${LLM_MODEL:-默认}）"
echo "数据目录 : $DATA_DIR"
echo

# ---------- 先起 AI 服务 ----------
"$PY" -m uvicorn app.main:app --host 127.0.0.1 --port "$AI_PORT" &
AI_PID=$!

# 两个进程一起退出：只 kill 一个会留下孤儿进程占着端口，下次启动直接 EADDRINUSE
cleanup() {
  echo
  echo "正在停止…"
  kill "$AI_PID" 2>/dev/null || true
  [ -n "${APP_PID:-}" ] && kill "$APP_PID" 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# 等 AI 服务就绪（最多 60 秒）：索引首次构建可能要几十秒
# 注意：不能只看 /health 通不通 —— 端口被**别的旧进程**占着时，探测同样会成功，
# 然后 SpringBoot 就把请求转给了那个旧进程（代码是上一版），排查起来极其费劲。
# 所以每一步都确认「我们的子进程还活着」。
echo -n "等待 AI 服务就绪"
for _ in $(seq 1 60); do
  if ! kill -0 "$AI_PID" 2>/dev/null; then
    echo " ✗"
    echo "AI 服务启动失败（端口 $AI_PORT 可能已被占用）："
    echo "  Windows: netstat -ano | findstr :$AI_PORT   然后 taskkill /PID <pid> /F"
    echo "  macOS/Linux: lsof -i :$AI_PORT"
    exit 1
  fi
  if "$PY" - "$AI_PORT" <<'EOF' 2>/dev/null
import sys, urllib.request
port = sys.argv[1]
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # 绕过系统代理
try:
    opener.open(f"http://127.0.0.1:{port}/health", timeout=2).read()
except Exception:
    sys.exit(1)
EOF
  then
    echo " ✓"
    break
  fi
  echo -n "."
  sleep 1
done

# ---------- 再起 SpringBoot ----------
JAVA_BIN="java"
[ -n "${JAVA_HOME:-}" ] && [ -x "$JAVA_HOME/bin/java" ] && JAVA_BIN="$JAVA_HOME/bin/java"
"$JAVA_BIN" -jar "$JAR" --server.port="$PORT" --app.ai.base-url="$AI_BASE_URL" &
APP_PID=$!

echo
echo "打开 http://127.0.0.1:$PORT/  （Ctrl+C 一起停止）"
wait "$APP_PID"
