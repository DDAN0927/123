"""依赖清单与代码实际用法的对齐检查。

起因是一个真实事故：为了瘦身，从 `requirements.txt` 删掉了 5 个「零引用」的包，
其中 `streamlit` 顺带把 `python-multipart` 装了进来。删掉之后，
`/api/knowledge/upload` 的 `UploadFile` 路由在**导入阶段**就抛
`RuntimeError: Form data requires "python-multipart" to be installed`，
本地因为 venv 里还留着旧包所以毫无察觉，线上容器直接起不来。

这类「隐式传递依赖」光靠 `grep 有没有 import` 是查不出来的，
所以这里把两条不变式钉死在测试里。
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
REQ = (ROOT / "requirements.txt").read_text(encoding="utf-8")

# 注释掉的行不算声明
DECLARED = {
    re.split(r"[<>=!~\[;\s]", line.strip(), maxsplit=1)[0].lower().replace("_", "-")
    for line in REQ.splitlines()
    if line.strip() and not line.strip().startswith("#")
}


def _app_sources() -> list[Path]:
    return [p for p in APP.rglob("*.py") if "__pycache__" not in p.parts]


def test_upload_routes_have_multipart_declared():
    """用了 UploadFile / File() / Form() 就必须声明 python-multipart。"""
    uses_upload = any(
        re.search(r"\b(UploadFile|File\(|Form\()", p.read_text(encoding="utf-8")) for p in _app_sources()
    )
    assert uses_upload, "预期知识库上传接口仍在用 UploadFile；若已移除，本用例可删"
    assert "python-multipart" in DECLARED, (
        "app/ 里用了 UploadFile，但 requirements.txt 没有声明 python-multipart —— "
        "FastAPI 会在导入阶段直接抛 RuntimeError，容器起不来"
    )


def test_no_dependency_on_removed_packages():
    """已被移除的包不允许再被 import，否则又会变成隐式依赖。"""
    removed = ["streamlit", "folium", "edge_tts", "pypinyin"]
    hits = []
    for p in _app_sources():
        text = p.read_text(encoding="utf-8")
        for name in removed:
            if re.search(rf"^\s*(?:from|import)\s+{name}\b", text, re.MULTILINE):
                hits.append(f"{p.relative_to(ROOT)} -> {name}")
    assert not hits, "以下文件仍依赖已移除的包：" + ", ".join(hits)


def test_requirements_has_no_duplicate_pins():
    """同一个包写两次且版本区间不一致，会让 pip 的解析结果变得不可预测。"""
    names = [
        re.split(r"[<>=!~\[;\s]", line.strip(), maxsplit=1)[0].lower().replace("_", "-")
        for line in REQ.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    dupes = {n for n in names if names.count(n) > 1}
    assert not dupes, f"requirements.txt 里重复声明：{dupes}"
