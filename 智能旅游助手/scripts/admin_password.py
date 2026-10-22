"""统一的管理员密码设置脚本（本地数据卷 / 已发布站点两种模式）。

为什么要两个模式
----------------
管理员账号由 `ensure_default_admin()` 在**首次启动**时写入 SQLite
（`$DATA_DIR/travel.db` 的 `users` 表），之后只在账号不存在时创建。所以：

* 改 `.env` 里的 `ADMIN_PASSWORD` 只对「还没建过账号」的全新环境有效；
* 已经存在账号的环境（本地 data/、线上数据卷），必须**主动改密码**才生效。

用法：
    # 本地：直接改 SQLite 里 admin 的密码哈希
    python scripts/admin_password.py --local <新密码>

    # 线上：走 /api/auth/change-password 接口
    python scripts/admin_password.py --remote <站点根地址> <新密码> [旧密码]
    # 旧密码省略时从 deploy/.env 的 ADMIN_PASSWORD 读取

脚本只打印状态码与结果，不回显任何密码。
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 显式绕过系统代理：本机若配了 HTTP 代理，直连公网站点更稳（代理常会拦截或改写请求）
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


# ---------------------------------------------------------------- 公共


def _deploy_env() -> dict:
    env = ROOT / "deploy" / ".env"
    out = {}
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    return out


# ---------------------------------------------------------------- 本地模式


def set_local(new_pw: str) -> int:
    from app import db, store
    from app.config import settings

    username = settings.admin_username
    existed = store.set_user_password(username, new_pw, role="admin")

    print(f"→ 数据目录: {settings.data_dir}")
    print(f"→ 数据库: {db.db_path()}")
    print(f"→ 账号: {username}（{'已存在，密码已重置' if existed else '不存在，已新建'}）")
    print("✅ 本地管理员密码已更新")
    return 0


# ---------------------------------------------------------------- 线上模式


def _post(base: str, path: str, payload: dict, token: str = "") -> tuple[int, str]:
    req = urllib.request.Request(
        base.rstrip("/") + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with _OPENER.open(req, timeout=40) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")[:300]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:300]
    except Exception as e:
        return 0, f"网络异常: {e}"


def set_remote(base: str, new_pw: str, old_pw: str) -> int:
    cfg = _deploy_env()
    username = cfg.get("ADMIN_USERNAME", "admin")
    if not old_pw:
        old_pw = cfg.get("ADMIN_PASSWORD", "")
    if not old_pw:
        print("❌ 未提供旧密码，且 deploy/.env 中也没有 ADMIN_PASSWORD")
        return 2

    print(f"→ 站点: {base}")
    print(f"→ 账号: {username}")

    code, body = _post(base, "/api/auth/login", {"username": username, "password": old_pw})
    print(f"   登录（旧密码）: HTTP {code}")
    if code != 200:
        print(f"   ❌ 旧密码登录失败，无法改密。响应: {body}")
        print("   提示：若旧密码确实不对，可改 deploy/.env 的 ADMIN_PASSWORD 后重新发布，")
        print("        并确认发布包里不含 data/users.json（否则会沿用旧账号）。")
        return 1
    token = json.loads(body)["token"]

    code, body = _post(
        base, "/api/auth/change-password", {"old_password": old_pw, "new_password": new_pw}, token
    )
    print(f"   修改密码: HTTP {code} — {body}")
    if code != 200:
        return 1

    code, _ = _post(base, "/api/auth/login", {"username": username, "password": new_pw})
    print(f"   用新密码复核登录: HTTP {code}")
    if code != 200:
        print("   ❌ 新密码登录失败")
        return 1

    print("✅ 线上管理员密码已更新")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="设置管理员密码（本地 / 线上）")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--local", action="store_true", help="改本地 data/users.json 里的 admin 密码")
    g.add_argument("--remote", metavar="站点根地址", help="改已发布站点的 admin 密码")
    ap.add_argument("new_password", help="新密码")
    ap.add_argument("old_password", nargs="?", default="", help="旧密码（仅 --remote，可省略）")
    a = ap.parse_args()

    if a.local:
        return set_local(a.new_password)
    return set_remote(a.remote, a.new_password, a.old_password)


if __name__ == "__main__":
    sys.exit(main())
