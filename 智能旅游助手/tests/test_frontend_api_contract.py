"""前端请求字段名必须与后端 JSON 契约一致（SNAKE_CASE）。

为什么需要这条测试：后端 `application.yml` 里
`spring.jackson.property-naming-strategy: SNAKE_CASE`，全站接口字段是
`old_password` / `start_date` / `day_index` 这种写法。前端如果写成
`oldPassword`，Jackson 解不出字段 → 服务端返回
「oldPassword 不能为空」，现象是「点了保存报字段不能为空」，
而界面上的输入框明明是填好的。

这个 bug 曾真实发生过（改密弹窗），而且 MockMvc 测试与打桩探针都拦不住：
前者直接发 snake_case，后者把请求原样吞下不做校验。所以在源码层面做一道静态检查。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "frontend" / "static" / "assets" / "js" / "app.js"
APP_YML = ROOT / "server" / "src" / "main" / "resources" / "application.yml"

CALL_RE = re.compile(r"api(?:Post|Put|Patch)\(\s*(?:`[^`]*`|\"[^\"]*\")\s*,\s*")
CAMEL_RE = re.compile(r"^[a-z]+[A-Z]")


def _naming_strategy() -> str:
    text = APP_YML.read_text(encoding="utf-8")
    m = re.search(r"property-naming-strategy:\s*(\w+)", text)
    return (m.group(1) if m else "").upper()


def _payload_blocks(js: str) -> list[str]:
    """取出所有 apiPost/apiPut/apiPatch 的内联对象字面量（不含外层大括号）。"""
    blocks: list[str] = []
    for m in CALL_RE.finditer(js):
        i = m.end()
        if i >= len(js) or js[i] != "{":
            continue
        depth = 0
        quote = ""
        for j in range(i, len(js)):
            c = js[j]
            if quote:
                if c == "\\":
                    continue
                if c == quote:
                    quote = ""
                continue
            if c in "\"'`":
                quote = c
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    blocks.append(js[i + 1 : j])
                    break
    return blocks


def _top_level_keys(block: str) -> list[str]:
    """只取对象第一层的键名，跳过嵌套对象、字符串与注释。"""
    keys: list[str] = []
    depth = 0
    quote = ""
    i = 0
    while i < len(block):
        c = block[i]
        if quote:
            if c == "\\":
                i += 2
                continue
            if c == quote:
                quote = ""
            i += 1
            continue
        if c in "\"'`":
            quote = c
            i += 1
            continue
        if block.startswith("//", i):
            nl = block.find("\n", i)
            i = len(block) if nl < 0 else nl + 1
            continue
        if c in "{[":
            depth += 1
        elif c in "}]":
            depth -= 1
        elif c == ":" and depth == 0:
            m = re.search(r"([A-Za-z_$][\w$]*)\s*$", block[:i])
            if m:
                keys.append(m.group(1))
        i += 1
    return keys


def test_app_js_exists() -> None:
    assert APP_JS.is_file(), f"找不到前端脚本：{APP_JS}"


@pytest.mark.skipif(_naming_strategy() != "SNAKE_CASE", reason="后端未使用 SNAKE_CASE 命名策略")
def test_inline_post_bodies_use_snake_case() -> None:
    js = APP_JS.read_text(encoding="utf-8")
    bad: list[str] = []
    for block in _payload_blocks(js):
        for key in _top_level_keys(block):
            if CAMEL_RE.match(key):
                bad.append(key)
    assert not bad, f"这些请求字段名是 camelCase，后端 SNAKE_CASE 策略下会被解成 null：{sorted(set(bad))}"


def test_change_password_uses_backend_field_names() -> None:
    js = APP_JS.read_text(encoding="utf-8")
    m = re.search(r"apiPost\(\s*[\"'`]/api/auth/change-password[\"'`]\s*,\s*(\{[^}]*\})", js)
    assert m, "找不到改密请求"
    body = m.group(1)
    assert "old_password" in body and "new_password" in body, f"改密请求字段不对：{body}"
