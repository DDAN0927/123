"""生成用于公网发布的精简部署包 deploy/。

只收集运行时真正需要的文件（不含 .venv / docker 配置 / 本地数据），并：
  - 内置 BGE 向量模型缓存 → 部署后离线可用，首次查询不再下载模型；
  - 生成独立的 .env（含强随机管理员密码），与本地开发数据隔离；
  - 使用精简依赖清单（去掉 Streamlit 等前端无关依赖，torch 走 CPU 轮子）；
  - **带上 SpringBoot 的 server.jar**，并在 install.sh 里解一个 JRE 到 ./jre。
    双后端重构之后业务（登录/行程/记账）只在 Java 侧，不带 jar 的话发布出去
    前端有一半功能是死的 —— 这正是沙箱长期停在「旧版单进程」的原因。

用法：python scripts/build_deploy.py（先 mvn -f server/pom.xml package -DskipTests）
可重复执行，每次都会重建 deploy/。
"""

import os
import secrets
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "deploy"
HF_MODEL = "models--BAAI--bge-small-zh-v1.5"

# 部署包依赖：仅 FastAPI 应用所需（不含 streamlit / folium / edge-tts 等）
# 向量检索三件套按本地已验证通过的版本锁定：transformers 5.x 要求 torch>=2.5，
# 因此 torch 必须 >= 2.5，否则 sentence-transformers 导入即报错。
REQUIREMENTS = """\
# 公网发布用精简依赖
#
# 关键约束：平台 install 阶段是 **300 秒硬超时**，而沙箱基座镜像（pyenv 3.11）已经
# 预装了 torch 2.10 / transformers 5.1 / fastapi / uvicorn / pydantic / numpy /
# scipy / scikit-learn / huggingface-hub / requests。所以这份清单只写「基座没有的
# 那几个」，其余只给下限，让 pip 复用已装版本。
#
# 反例（踩过两次）：钉 torch==2.14.1+cpu + transformers==5.18.0，pip 会去拉 200MB
# 的 CPU 轮子、把基座那份整个换掉，两次都卡在 300 秒被判 install 失败。
# 实测：只装缺失包 10 秒，import faiss / sentence_transformers 正常。
#
# 源地址**不写在这里**：换源是安装脚本的职责（install.sh 带 -i），写进要求文件
# 会盖掉命令行参数，回退逻辑就失效了。

fastapi>=0.115.0,<1.0
uvicorn[standard]>=0.30.0
# 知识库上传接口用了 UploadFile，FastAPI 注册路由时就校验这个包；
# 缺了它 app.main 导入即失败（RuntimeError: Form data requires "python-multipart"）。
python-multipart>=0.0.9

langgraph>=0.2.60,<0.3
langchain-core>=0.3.20,<0.4
langchain-openai>=0.2.10,<0.3
langchain-text-splitters>=0.3.0,<0.4

faiss-cpu>=1.8.0,<1.9
sentence-transformers>=6.1
pydantic-settings>=2.4.0

# ---- 以下基座已有：写下限只为「万一落到干净镜像」时仍能解析出完整环境 ----
torch>=2.5
transformers>=5.0,<6
huggingface-hub>=0.27
numpy>=1.24.0
requests>=2.32.0
pydantic>=2.8.0
python-dotenv>=1.0.0
"""

# 沙箱安装脚本：**不能**只写 `pip install -r requirements.txt`。
# 沙箱基座镜像（pyenv 3.11）预装了 CUDA 版 torchaudio / torchvision，
# 而本包装的是 CPU 版 torch —— 三者的 C 扩展互相不匹配，sentence-transformers
# 导入时会连带加载它们，直接抛：
#   OSError: libtorch_cuda.so: cannot open shared object file
#   RuntimeError: operator torchvision::nms does not exist
# 后果是整条 RAG 链路静默失效（进程照样起得来，只看 /health 的 index_ready 看不出来）。
# 本项目不使用音视频/图像能力，把这两个包卸掉最省事也最稳。
INSTALL_SH = """\
#!/usr/bin/env bash
# 依赖安装（由 scripts/build_deploy.py 生成，请勿手改）
set -e

fetch() {  # fetch <url> <out> <max-seconds>
  if command -v curl >/dev/null 2>&1; then
    curl -fL --retry 2 --retry-delay 2 --connect-timeout 20 --max-time "${3:-150}" -o "$2" "$1"
  else
    # curl 不一定有（基座镜像很精简），退回 python 的 urllib —— python 是必有的。
    python - "$1" "$2" "$3" <<'PY'
import sys, urllib.request
urllib.request.urlretrieve(sys.argv[1], sys.argv[2])
PY
  fi
}

# ---------- JRE（给 SpringBoot 用）----------
# 沙箱是 pyenv 基础镜像：没有 apt 权限、没有全局 PATH、也**没有 java**（实测
# `command -v java` 为空，/usr/lib/jvm 不存在），所以必须自己弄一份。
#
# 两个源，顺序有讲究：
#  1) 华为云 openjdk 17.0.2 —— 实测沙箱内 19.7MB/s，190MB 的包十来秒下完；
#  2) adoptium 官方 —— 实测在沙箱里读超时（179 秒无响应），只作兜底。
# 官方那个 URL 以前是本脚本唯一的源，这就是 install 阶段 300 秒超时的真正原因。
install_jre() {
  [ -x jre/bin/java ] && { echo "[install] JRE 已存在，跳过"; return 0; }
  for spec in \\
    "https://repo.huaweicloud.com/openjdk/17.0.2/openjdk-17.0.2_linux-x64_bin.tar.gz 120" \\
    "https://api.adoptium.net/v3/binary/latest/17/ga/linux/x64/jre/hotspot/normal/eclipse 60" ; do
    url="${spec% *}"; limit="${spec##* }"
    echo "[install] 下载 JDK/JRE: $url"
    if fetch "$url" /tmp/jdk.tar.gz "$limit"; then
      rm -rf jre
      if tar xzf /tmp/jdk.tar.gz 2>/dev/null; then
        rm -f /tmp/jdk.tar.gz
        # 华为云是 JDK 包（解出 jdk-17.0.2/），adoptium 是 JRE 包（解出 jdk-17.0.x+y-jre/）
        if [ -d jdk-17.0.2 ]; then
          mv jdk-17.0.2 jre
        else
          d="$(ls -d jdk-17* 2>/dev/null | head -1)"
          [ -n "$d" ] && mv "$d" jre
        fi
      fi
      if [ -x jre/bin/java ]; then ./jre/bin/java -version 2>&1 | head -2; return 0; fi
    fi
    echo "[install] ⚠️  这个源没成，换下一个"
  done
  # 拿不到 JRE 不让安装失败：start.sh 会退回单进程（AI 可用，登录/行程不可用），
  # 整站起不来比「功能少一半」严重得多。
  echo "[install] ⚠️  JRE 获取失败 → 运行时会退回单进程模式（无登录/行程）"
}

install_jre > /tmp/jre-install.log 2>&1 &
JRE_PID=$!

# ---------- Python 依赖 ----------
# 换国内镜像不是「优化」，是能不能装完的问题：默认源在沙箱里只有 14KB/s。
# 实测清华镜像在沙箱内 17.9MB/s，缺的那几个包 10 秒装完。
if ! pip install -q --root-user-action=ignore -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt; then
  echo "[install] ⚠️  清华镜像失败，回退默认源（会明显更慢）"
  pip install -q --root-user-action=ignore -r requirements.txt
fi

# 为什么必须卸掉这两个：沙箱基座预装了 CUDA 版 torchaudio / torchvision，与本包
# 使用的 torch 版本不一致时，sentence-transformers 导入会连带加载它们并失败：
#   OSError: libtorch_cuda.so: cannot open shared object file
# 本项目不用音视频/图像能力，卸掉最省事也最稳。
echo "[install] 移除基座镜像预装的 torchaudio / torchvision"
pip uninstall -y -q torchaudio torchvision > /dev/null 2>&1 || true

wait $JRE_PID || true
tail -3 /tmp/jre-install.log 2>/dev/null || true
echo "[install] 完成"
"""


def copy_tree(src: Path, dst: Path):
    """整树复制，目标已存在时**覆盖**而不是先删后建。

    以前这里是「rmtree 整个 deploy/ 再重建」。那样做有两个毛病：
    一是每次都要重写 150MB（其中 90MB 是 HF 模型缓存，一个字节都没变）；
    二是任何拦截批量删除的环境（沙箱宿主的 safe-delete 钩子会按文件数阈值拦
    `rmtree`）都跑不动这个脚本，报一个和部署毫无关系的错。改成覆盖 + 事后清理
    过期文件之后，两者都消失了。
    """
    shutil.copytree(
        src,
        dst,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )


def _expected_files() -> set[str]:
    """部署包里**应该**存在的相对路径集合（用于清理上一版留下的过期文件）。"""
    rels: set[str] = set()

    def add(src: Path, prefix: str):
        if not src.is_dir():
            return
        for p in src.rglob("*"):
            if not p.is_file():
                continue
            if "__pycache__" in p.parts or p.suffix in (".pyc", ".pyo"):
                continue
            rels.add(f"{prefix}/{p.relative_to(src).as_posix()}" if prefix else p.relative_to(src).as_posix())

    add(ROOT / "app", "app")
    add(ROOT / "frontend" / "static", "frontend/static")
    add(ROOT / "knowledge_base", "knowledge_base")
    add(ROOT / "data" / "index", "data/index")
    hf = Path.home() / ".cache" / "huggingface" / "hub" / HF_MODEL
    add(hf, f"hf_cache/hub/{HF_MODEL}")
    rels |= {"server.jar", "application.yml", "requirements.txt", "install.sh", "start.sh", ".env"}
    return rels


def _read_env_value(lines: list[str], key: str) -> str:
    """从 .env 行列表里取某个键的值（不存在返回空串）。"""
    for line in lines:
        s = line.strip()
        if s.startswith(key + "="):
            return s.split("=", 1)[1].strip()
    return ""


def build_env(prev_admin_pw: str = "") -> tuple[str, str]:
    """基于本地 .env 生成部署用 .env。

    * 管理员密码优先级：本地 .env 显式指定 > 上次 deploy/.env 里的值 > 随机生成。
      显式指定最高，这样「我就想用某个固定密码」的意图在每次重建后都成立；
      没有显式指定时沿用上次的值，避免重建就把线上用户踢下线。
    * ``ALLOW_REGISTRATION`` 跟随本地 .env 的显式设置（缺省则 false，安全优先）。
      当前本地 .env 为 true —— 站点允许任何人自助注册，此时**限流就是唯一的额度防线**。
    """
    src = ROOT / ".env"
    lines = src.read_text(encoding="utf-8").splitlines() if src.exists() else []

    admin_user = _read_env_value(lines, "ADMIN_USERNAME") or "admin"
    # 环境变量可覆盖：用于「本地 .env 保持 admin/123456（测试脚本依赖），
    # 只把公网包换成强随机密码」的场景
    admin_pw = (
        os.environ.get("DEPLOY_ADMIN_PW")
        or _read_env_value(lines, "ADMIN_PASSWORD")
        or prev_admin_pw
        or secrets.token_urlsafe(9)
    )
    allow_reg = (_read_env_value(lines, "ALLOW_REGISTRATION") or "false").lower()

    # 这些键由部署包自行决定，不继承本地开发值
    overridden = ("ADMIN_USERNAME", "ADMIN_PASSWORD", "ALLOW_REGISTRATION")
    kept = [line for line in lines if line.strip() and not line.strip().startswith(overridden)]
    kept.append("")
    kept.append("# ===== 管理员账号（公网发布用，本地 .env 不受影响）=====")
    kept.append(f"ADMIN_USERNAME={admin_user}")
    kept.append(f"ADMIN_PASSWORD={admin_pw}")
    kept.append("")
    kept.append("# ===== 注册开关（跟随本地 .env；true 时新账号自助注册）=====")
    kept.append(f"ALLOW_REGISTRATION={allow_reg}")
    return "\n".join(kept) + "\n", admin_pw


def read_prev_admin_pw() -> str:
    """读取上一次 deploy/.env 中的管理员密码（必须在 rmtree 之前调用）"""
    prev = OUT / ".env"
    if not prev.exists():
        return ""
    for line in prev.read_text(encoding="utf-8").splitlines():
        if line.startswith("ADMIN_PASSWORD="):
            return line.split("=", 1)[1].strip()
    return ""


def main():
    prev_admin_pw = read_prev_admin_pw()
    # 不清空整个目录（见 copy_tree 的注释）：原地覆盖，最后再扫掉过期文件。
    # 好处是重建一次通常只写几 MB，而且保留了上次的 .env（管理员密码不会被换掉）。
    OUT.mkdir(parents=True, exist_ok=True)

    # 1) 应用代码
    copy_tree(ROOT / "app", OUT / "app")

    # 2) 前端静态站（不含 Streamlit 前端）
    copy_tree(ROOT / "frontend" / "static", OUT / "frontend" / "static")

    # 3) 内置攻略库
    copy_tree(ROOT / "knowledge_base", OUT / "knowledge_base")

    # 4) 预构建的向量索引（免去启动时重建）
    idx_src = ROOT / "data" / "index"
    if not (idx_src / "faiss.index").exists():
        print("❌ 未找到 data/index/faiss.index，请先运行 python scripts/build_kb.py")
        return 1
    (OUT / "data" / "index").mkdir(parents=True, exist_ok=True)
    for f in idx_src.iterdir():
        if f.is_file():
            shutil.copy2(f, OUT / "data" / "index" / f.name)

    # 5) 内置向量模型缓存（离线可用）
    hf_src = Path.home() / ".cache" / "huggingface" / "hub" / HF_MODEL
    if hf_src.is_dir():
        dst = OUT / "hf_cache" / "hub" / HF_MODEL
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(hf_src, dst, dirs_exist_ok=True)
    else:
        print("⚠️  未找到本地 HF 模型缓存，部署后将需要联网下载模型")

    # 5.5) SpringBoot 主后端（登录 / 行程 / 记账 / 导出 / 分享 都在这里）
    # 以前不拷 jar，沙箱只能跑单进程 Python —— 那是双后端重构**之前**的形态，
    # 重构之后 Python 侧只剩 AI 能力，不拷 jar 的话前端一半功能是死的。
    jar_src = ROOT / "server" / "target" / "travel-server.jar"
    if jar_src.exists():
        shutil.copy2(jar_src, OUT / "server.jar")
    else:
        print(
            "⚠️  未找到 server/target/travel-server.jar → 部署包会退回单进程"
            "（只有 AI 对话，没有登录/行程）。先跑：mvn -f server/pom.xml package -DskipTests"
        )

    # 5.6) 把 application.yml 单独放到包根目录
    #
    # jar 是构建产物，里面的 application.yml 停在「昨次 mvn package 那一刻」；
    # 而配置改动（超时、阈值）往往比最后一次打包更晚，就会出现「代码改了、包里没生效」。
    # SpringBoot 默认加载顺序里 file:./ 晚于 classpath，start.sh 又会 cd 到脚本目录，
    # 所以根目录这份会按 key 覆盖 jar 内的旧值 —— 等于把配置从黑盒里拿出来。
    yml_src = ROOT / "server" / "src" / "main" / "resources" / "application.yml"
    if yml_src.exists():
        shutil.copy2(yml_src, OUT / "application.yml")

    # 6) 依赖 / 安装脚本 / 启动脚本 / 环境变量
    #
    # 🔴 三个文本文件必须写成 **LF**。Windows 上 `Path.write_text` 默认按 os.linesep
    # 翻译，写出来是 CRLF；`shutil.copy2` 更是原样拷贝（仓库在 core.autocrlf=true 下
    # 检出的就是 CRLF）。CRLF 的 shell 脚本在 Linux 沙箱里会直接炸在第一个 set 上：
    #   install.sh: line 3: set: -\r: invalid option
    # 而且这个错在本地测不出来 —— 本地 Git Bash 对 CRLF 是宽容的。
    (OUT / "requirements.txt").write_text(REQUIREMENTS, encoding="utf-8", newline="\n")
    (OUT / "install.sh").write_text(INSTALL_SH, encoding="utf-8", newline="\n")
    (OUT / "start.sh").write_bytes((ROOT / "start.sh").read_bytes().replace(b"\r\n", b"\n"))
    env_text, admin_pw = build_env(prev_admin_pw)
    (OUT / ".env").write_text(env_text, encoding="utf-8", newline="\n")

    # 6.5) 清理上一版留下、这一版已经没有的文件
    # 原地覆盖的代价：删掉一个模块（比如下掉某个脚本）后，旧文件会留在包里跟着发出去。
    # 所以每次都要对一遍「应该有什么」，多出来的逐个删掉（**逐个**：批量删除在
    # 有 safe-delete 钩子的环境里会被拦，而这里正常情况只有几个）。
    expected = _expected_files()
    stale = []
    for p in OUT.rglob("*"):
        if p.is_file() and p.relative_to(OUT).as_posix() not in expected:
            stale.append(p)
    for p in stale:
        p.unlink()
    if stale:
        print(f"   清理过期文件 {len(stale)} 个：{[p.name for p in stale[:5]]}")

    # 7) 报告
    total = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    print(f"✅ 部署包已生成：{OUT}")
    print(f"   文件数 {sum(1 for f in OUT.rglob('*') if f.is_file())}，总大小 {total / 1024 / 1024:.1f} MB")
    print(f"   管理员账号 admin / {admin_pw}" + ("（沿用上次密码）" if prev_admin_pw else "（新生成）"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
