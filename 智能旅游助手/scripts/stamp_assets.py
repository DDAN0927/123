#!/usr/bin/env python3
"""给静态资源引用打版本号，避免浏览器/网关缓存住旧 app.js。

背景：线上反馈「点了没反应」，排查下来是拿到的还是发布前的 app.js ——
即使源站回了 no-store，中间层（平台网关、运营商代理、App 内置 WebView）
仍可能缓存。资源 URL 带上 ?v=<build> 后，新版本的 URL 就是新 URL，
没有任何缓存能挡住。

用法：
    python scripts/stamp_assets.py                 # 用 app.js 里已有的 BUILD
    python scripts/stamp_assets.py --stamp 2026-11-25a   # 同时改 app.js 的 BUILD

约定：BUILD 的唯一真源是 frontend/static/assets/js/app.js 里的
`const BUILD = "..."`；本脚本把它写到所有 HTML 的 css/js 引用上。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "frontend" / "static"
APP_JS = STATIC / "assets" / "js" / "app.js"

BUILD_RE = re.compile(r'(const BUILD = ")([^"]+)(";)')
# 只匹配本站相对资源：assets/css|js 下的文件，可已带 ?v=xxx
ASSET_RE = re.compile(r"(?P<url>assets/(?:css|js)/[\w.-]+\.(?:css|js))(?:\?v=[\w.-]+)?")


def read_build() -> str:
    src = APP_JS.read_text(encoding="utf-8")
    m = BUILD_RE.search(src)
    if not m:
        raise SystemExit(f'在 {APP_JS} 里找不到 `const BUILD = "...";`')
    return m.group(2)


def write_build(stamp: str) -> None:
    src = APP_JS.read_text(encoding="utf-8")
    new, n = BUILD_RE.subn(rf"\g<1>{stamp}\g<3>", src)
    if n != 1:
        raise SystemExit("BUILD 常量替换失败")
    APP_JS.write_text(new, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="给静态资源引用打版本号")
    ap.add_argument("--stamp", help="新的构建标记，同时写回 app.js 的 BUILD")
    ap.add_argument("--check", action="store_true", help="只检查，不写文件（CI 用）")
    args = ap.parse_args(argv)

    stamp = args.stamp or read_build()
    if not re.fullmatch(r"[\w.-]+", stamp):
        raise SystemExit(f"非法的 stamp：{stamp!r}（只允许字母数字与 . _ -）")

    if args.stamp and not args.check:
        write_build(stamp)

    pages = sorted(STATIC.glob("*.html"))
    changed: list[str] = []
    total_refs = 0
    stale: list[str] = []
    for page in pages:
        html = page.read_text(encoding="utf-8")
        refs = ASSET_RE.findall(html)
        total_refs += len(refs)
        new = ASSET_RE.sub(lambda m: f"{m.group('url')}?v={stamp}", html)
        if new != html:
            if args.check:
                stale.append(page.name)
            else:
                page.write_text(new, encoding="utf-8")
                changed.append(page.name)

    if args.check:
        if stale:
            print(f"❌ 这些页面的资源版本号不是 {stamp}：{', '.join(stale)}")
            return 1
        print(f"✅ {len(pages)} 个页面的 {total_refs} 处资源引用都是 ?v={stamp}")
        return 0

    print(f"stamp = {stamp}")
    print(f"扫描 {len(pages)} 个页面，{total_refs} 处 css/js 引用")
    print(f"改写 {len(changed)} 个页面：{', '.join(changed) if changed else '（已是最新）'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
