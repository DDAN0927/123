"""生成用于公网发布的精简部署包 deploy/。

只收集运行时真正需要的文件（不含 .venv / docker 配置 / 本地数据），并：
  - 内置 BGE 向量模型缓存 → 部署后离线可用，首次查询不再下载模型；
  - 生成独立的 .env（含强随机管理员密码），与本地开发数据隔离；
  - 使用精简依赖清单（去掉 Streamlit 等前端无关依赖，torch 走 CPU 轮子）。

用法：python scripts/build_deploy.py
可重复执行，每次都会重建 deploy/。
"""

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
# 公网发布用精简依赖（torch 走 CPU 轮子，体积远小于默认 CUDA 版）
--extra-index-url https://download.pytorch.org/whl/cpu

fastapi>=0.115.0,<1.0
uvicorn[standard]>=0.30.0
# 知识库上传接口用了 UploadFile，FastAPI 注册路由时就校验这个包；
# 缺了它 app.main 导入即失败（RuntimeError: Form data requires "python-multipart"）。
# 之前它由 streamlit 顺带装上，删掉 streamlit 后必须显式声明。
python-multipart>=0.0.9

langgraph>=0.2.60,<0.3
langchain-core>=0.3.20,<0.4
langchain-openai>=0.2.10,<0.3
langchain-text-splitters>=0.3.0,<0.4

numpy>=1.24.0,<2.0
faiss-cpu>=1.8.0,<1.9

torch==2.14.1+cpu
transformers==5.18.0
sentence-transformers==6.1.0
huggingface-hub==1.33.0

requests>=2.32.0
pydantic>=2.8.0
pydantic-settings>=2.4.0
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
pip install -r requirements.txt
echo "[install] 移除基座镜像预装的 CUDA 版 torchaudio / torchvision"
pip uninstall -y torchaudio torchvision || true
"""


def copy_tree(src: Path, dst: Path):
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"))


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
    admin_pw = _read_env_value(lines, "ADMIN_PASSWORD") or prev_admin_pw or secrets.token_urlsafe(9)
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
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    # 1) 应用代码
    copy_tree(ROOT / "app", OUT / "app")

    # 2) 前端静态站（不含 Streamlit 前端）
    (OUT / "frontend").mkdir()
    copy_tree(ROOT / "frontend" / "static", OUT / "frontend" / "static")

    # 3) 内置攻略库
    copy_tree(ROOT / "knowledge_base", OUT / "knowledge_base")

    # 4) 预构建的向量索引（免去启动时重建）
    idx_src = ROOT / "data" / "index"
    if not (idx_src / "faiss.index").exists():
        print("❌ 未找到 data/index/faiss.index，请先运行 python scripts/build_kb.py")
        return 1
    (OUT / "data" / "index").mkdir(parents=True)
    for f in idx_src.iterdir():
        if f.is_file():
            shutil.copy2(f, OUT / "data" / "index" / f.name)

    # 5) 内置向量模型缓存（离线可用）
    hf_src = Path.home() / ".cache" / "huggingface" / "hub" / HF_MODEL
    if hf_src.is_dir():
        dst = OUT / "hf_cache" / "hub" / HF_MODEL
        dst.parent.mkdir(parents=True)
        shutil.copytree(hf_src, dst)
    else:
        print("⚠️  未找到本地 HF 模型缓存，部署后将需要联网下载模型")

    # 6) 依赖 / 安装脚本 / 启动脚本 / 环境变量
    (OUT / "requirements.txt").write_text(REQUIREMENTS, encoding="utf-8")
    (OUT / "install.sh").write_text(INSTALL_SH.replace("\r\n", "\n"), encoding="utf-8")
    shutil.copy2(ROOT / "start.sh", OUT / "start.sh")
    env_text, admin_pw = build_env(prev_admin_pw)
    (OUT / ".env").write_text(env_text, encoding="utf-8")

    # 7) 报告
    total = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    print(f"✅ 部署包已生成：{OUT}")
    print(f"   文件数 {sum(1 for f in OUT.rglob('*') if f.is_file())}，总大小 {total / 1024 / 1024:.1f} MB")
    print(f"   管理员账号 admin / {admin_pw}" + ("（沿用上次密码）" if prev_admin_pw else "（新生成）"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
