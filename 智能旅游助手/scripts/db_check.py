"""存储层自测：SQLite 建表 / 旧数据迁移 / 持久化 / 并发 / 内容库。

设计要点：
- 全部离线、零成本：LLM_PROVIDER=mock，不调用真实大模型；
- 使用临时 DATA_DIR / KB_DIR，不污染真实 data/；
- 在导入 app 之前**预置旧版 JSON/JSONL 文件**，用来验证自动迁移真的生效；
- 同时覆盖 API 层（TestClient），确认 /api/notes 路由与鉴权接线正确。

运行：python scripts/db_check.py
"""

import json
import os
import sys
import tempfile
import threading
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="tc-dbcheck-"))
_DATA = _TMP / "data"
_KB = _TMP / "kb"
_DATA.mkdir(parents=True, exist_ok=True)
_KB.mkdir(parents=True, exist_ok=True)

# ---- 预置「旧版本」数据：迁移用例的数据源 -------------------------------------
_LEGACY_USER = {
    "legacy": {
        "username": "legacy",
        "salt": "abc123",
        "password_hash": "deadbeef",
        "role": "user",
        "created_at": 1000.0,
    }
}
(_DATA / "users.json").write_text(json.dumps(_LEGACY_USER, ensure_ascii=False), encoding="utf-8")

_FAV = [
    {
        "id": "f1",
        "title": "老收藏A",
        "content": "内容A",
        "session_id": "s1",
        "username": "legacy",
        "created_at": 1001.0,
    },
    {
        "id": "f2",
        "title": "老收藏B",
        "content": "内容B",
        "session_id": "",
        "username": "",
        "created_at": 1002.0,
    },
]
(_DATA / "favorites.jsonl").write_text(
    "\n".join(json.dumps(i, ensure_ascii=False) for i in _FAV) + "\n", encoding="utf-8"
)

_EVENTS = [
    {"type": "session", "session": {"id": "s1", "created_at": 1000.0}},
    {"type": "session_user", "session_id": "s1", "username": "legacy"},
    {"type": "message", "session_id": "s1", "role": "user", "content": "老问题", "ts": 1001.0},
    {"type": "message", "session_id": "s1", "role": "assistant", "content": "老回答", "ts": 1002.0},
]
(_DATA / "sessions.jsonl").write_text(
    "\n".join(json.dumps(e, ensure_ascii=False) for e in _EVENTS) + "\n", encoding="utf-8"
)

(_DATA / "stats.json").write_text(
    json.dumps(
        {"total_sessions": 7, "total_messages": 9, "agent_calls": {"planner": 3}, "likes": 5, "dislikes": 1},
        ensure_ascii=False,
    ),
    encoding="utf-8",
)

os.environ["DATA_DIR"] = str(_DATA)
os.environ["KB_DIR"] = str(_KB)
os.environ["LLM_PROVIDER"] = "mock"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "admin123"
os.environ["ALLOW_REGISTRATION"] = "true"
os.environ["RATE_LIMIT_ENABLED"] = "false"

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import db, store
from app import notes as notes_store

PASS = 0
FAIL = 0


def ok(name: str, cond: bool, detail: str = ""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"✅ {name}" + (f" — {detail}" if detail else ""))
    else:
        FAIL += 1
        print(f"❌ {name}" + (f" — {detail}" if detail else ""))


def _raises(fn) -> bool:
    """断言 fn 会抛异常（用于校验参数校验逻辑）"""
    try:
        fn()
        return False
    except Exception:
        return True


# ============================================================ 1. 建表与迁移

mig = db.init()
ok("首次 init 触发了迁移", mig.get("migrated") is True, str(mig))
ok("迁移导入了 1 个历史用户", mig.get("users") == 1, f"users={mig.get('users')}")
ok("迁移导入了 2 条历史收藏", mig.get("favorites") == 2, f"favorites={mig.get('favorites')}")
ok("迁移导入了 1 个历史会话", mig.get("sessions") == 1, f"sessions={mig.get('sessions')}")
ok("迁移导入了 2 条历史消息", mig.get("messages") == 2, f"messages={mig.get('messages')}")

mig2 = db.init()
ok("再次 init 不会重复迁移", mig2.get("migrated") is False, str(mig2))

ok("旧 users.json 已留档为 .imported", (_DATA / "users.json.imported").exists())
ok("旧 favorites.jsonl 已留档为 .imported", (_DATA / "favorites.jsonl.imported").exists())
ok("数据库文件落在 DATA_DIR 下", db.db_path().parent == _DATA, str(db.db_path()))

tables = {r["name"] for r in db.q("SELECT name FROM sqlite_master WHERE type='table'")}
for t in (
    "users",
    "sessions",
    "messages",
    "feedback",
    "favorites",
    "counters",
    "agent_calls",
    "notes",
    "meta",
):
    ok(f"表 {t} 已建立", t in tables)

# 迁移后的数据可读
ok("历史用户可查到", store.get_user("legacy") is not None)
legacy_favs = store.list_favorites(username="legacy")
ok("历史收藏按用户隔离正确", len(legacy_favs) == 1 and legacy_favs[0]["id"] == "f1", f"n={len(legacy_favs)}")
ok("历史收藏（无归属）也保留", len(store.list_favorites(username="")) == 1)

st = store.get_stats()
ok("历史统计计数已迁移", st["total_sessions"] == 7 and st["total_messages"] == 9, str(st))
ok("历史 likes/dislikes 已迁移", st["likes"] == 5 and st["dislikes"] == 1)
ok("历史 agent_calls 已迁移", st["agent_calls"].get("planner") == 3, str(st["agent_calls"]))

# ============================================================ 2. 会话与消息

s = store.get_or_create_session("sess-A")
ok(
    "新建会话返回完整结构",
    set(s) >= {"id", "messages", "created_at", "updated_at", "username"},
    str(sorted(s)),
)
ok("新会话消息为空", s["messages"] == [])

same = store.get_or_create_session("sess-A")
ok("同 id 重复获取不会重建", same["created_at"] == s["created_at"])

store.append_message("sess-A", "user", "北京三日游怎么安排")
store.append_message("sess-A", "assistant", "建议第一天去故宫")
got = store.get_session("sess-A")
ok(
    "消息按顺序持久化",
    [m["role"] for m in got["messages"]] == ["user", "assistant"],
    str([m["role"] for m in got["messages"]]),
)
ok("append_message 更新了 updated_at", got["updated_at"] >= got["created_at"])

store.set_session_user("sess-A", "legacy")
ok("会话可关联到用户", store.get_session("sess-A")["username"] == "legacy")

mine = store.list_user_sessions("legacy")
ids = {i["id"] for i in mine}
ok("用户会话列表包含新建的会话", "sess-A" in ids, str(sorted(ids)))
title = next(i["title"] for i in mine if i["id"] == "sess-A")
ok("会话标题取首条用户消息", title.startswith("北京三日游"), title)

listed = {i["id"]: i for i in store.list_sessions(limit=50)}
ok("运营会话列表含 message_count", listed["sess-A"]["message_count"] == 2)
ok(
    "运营会话列表含 preview（取最后一条）",
    "建议第一天去故宫" in listed["sess-A"]["preview"],
    listed["sess-A"]["preview"],
)

ok("不存在的会话返回 None", store.get_session("no-such-session") is None)
ok("给不存在的会话追加消息不报错", store.append_message("no-such-session", "user", "x") is None)

# 反馈
ok("不存在的会话记反馈返回 False", store.record_feedback("no-such", 1, "like") is False)
ok("存在的会话记反馈返回 True", store.record_feedback("sess-A", 1, "like") is True)
ok("点踩计数独立", store.get_stats()["dislikes"] == 1)

# ============================================================ 3. 收藏

fav = store.add_favorite("标题", "正文内容", session_id="sess-A", username="alice")
ok(
    "新增收藏返回 id/title/username",
    fav["id"] and fav["title"] == "标题" and fav["username"] == "alice",
    str(fav),
)

ok(
    "标题为空时取正文前 40 字",
    store.add_favorite("", "这是一段很长的正文内容用来测试标题回退逻辑")["title"].startswith("这是一段很长"),
)
ok("标题超长被截断到 60 字", len(store.add_favorite("啊" * 100, "x")["title"]) == 60)

ok("收藏按用户隔离", len(store.list_favorites(username="alice")) == 1)
ok("他人看不到 alice 的收藏", len(store.list_favorites(username="bob")) == 0)

ok("越权删除他人收藏失败", store.delete_favorite(fav["id"], username="bob") is False)
ok("越权删除后收藏仍在", len(store.list_favorites(username="alice")) == 1)
ok("本人删除成功", store.delete_favorite(fav["id"], username="alice") is True)
ok("删除后列表为空", len(store.list_favorites(username="alice")) == 0)
ok("删除不存在的收藏返回 False", store.delete_favorite("no-such") is False)

# ============================================================ 4. 用户

u, err = store.create_user("alice", "pw123456")
ok("创建用户成功", u is not None and err == "", err)
ok("重复用户名被拒绝", store.create_user("alice", "pw123456")[1] == "用户名已存在")
ok("空用户名被拒绝", store.create_user("", "pw")[1] == "用户名和密码不能为空")
ok("空密码被拒绝", store.create_user("bob", "")[1] == "用户名和密码不能为空")
ok("用户名前后空格被裁掉", store.create_user("  carol  ", "pw123456")[0]["username"] == "carol")

ok("正确密码可认证", store.authenticate("alice", "pw123456") is not None)
ok("错误密码不可认证", store.authenticate("alice", "wrong") is None)
ok("不存在的用户不可认证", store.authenticate("nobody", "x") is None)

ok("旧密码错误时改密失败", store.change_password("alice", "wrong", "newpw123")[0] is False)
ok("新密码为空时改密失败", store.change_password("alice", "pw123456", "")[0] is False)
ok("改密成功", store.change_password("alice", "pw123456", "newpw123")[0] is True)
ok("改密后旧密码失效", store.authenticate("alice", "pw123456") is None)
ok("改密后新密码可用", store.authenticate("alice", "newpw123") is not None)
ok("不存在的用户改密返回失败", store.change_password("nobody", "a", "b")[1] == "用户不存在")

ok("set_user_password 新建账号返回 False", store.set_user_password("ops", "opspw123") is False)
ok("set_user_password 重置已存在账号返回 True", store.set_user_password("ops", "opspw456") is True)
ok("set_user_password 结果可登录", store.authenticate("ops", "opspw456") is not None)

store.ensure_default_admin()
ok("默认管理员已创建", store.get_user("admin") is not None)
ok("默认管理员角色正确", store.get_user("admin")["role"] == "admin")
ok("默认管理员密码可登录", store.authenticate("admin", "admin123") is not None)
store.ensure_default_admin()
ok("重复 ensure_default_admin 幂等", store.authenticate("admin", "admin123") is not None)

usage = {r["username"]: r for r in store.list_users_usage()}
# legacy 名下有两个会话：迁移来的 s1，以及后面关联过去的 sess-A；各 2 条消息
ok("用户使用情况含 session_count", usage["legacy"]["session_count"] == 2, str(usage.get("legacy")))
ok("用户使用情况含 message_count", usage["legacy"]["message_count"] == 4)
ok("未使用的用户计数为 0", usage["alice"]["session_count"] == 0)

# ============================================================ 5. 并发写入

store.get_or_create_session("sess-CONC")
N_THREADS, PER_THREAD = 8, 25


def _writer(i: int):
    for j in range(PER_THREAD):
        store.append_message("sess-CONC", "user", f"t{i}-{j}")


threads = [threading.Thread(target=_writer, args=(i,)) for i in range(N_THREADS)]
for t in threads:
    t.start()
for t in threads:
    t.join()

conc = store.get_session("sess-CONC")
ok(
    "并发写入无丢失",
    len(conc["messages"]) == N_THREADS * PER_THREAD,
    f"期望 {N_THREADS * PER_THREAD}，实际 {len(conc['messages'])}",
)

# ============================================================ 6. 内容库

ok("内容库初始为空", notes_store.note_stats()["total"] == 0)
ok("空内容被拒绝", _raises(lambda: notes_store.add_note("manual", "t", "   ")))
ok("超长内容被拒绝", _raises(lambda: notes_store.add_note("manual", "t", "x" * 20001)))

n1 = notes_store.add_note(
    "xiaohongshu",
    "北京胡同咖啡地图",
    "南锣鼓巷有几家不错的咖啡店……",
    city="北京",
    tags="咖啡,胡同",
    url="https://example.com/a",
    author="小明",
    imported_by="admin",
)
n2 = notes_store.add_note(
    "douyin", "重庆火锅探店", "解放碑这家老火锅排队两小时……", city="重庆", tags="火锅", imported_by="admin"
)
n3 = notes_store.add_note("manual", "未分类随笔", "随手记一点东西", imported_by="admin")

ok("小红书来源被记录", n1["source"] == "xiaohongshu")
ok("抖音来源被记录", n2["source"] == "douyin")
ok("未知来源归一为 other", notes_store.add_note("weibo", "t", "微博来的内容")["source"] == "other")
ok("标题留空时取正文前 40 字", n3["title"] == "未分类随笔")

ok("按城市过滤", {n["id"] for n in notes_store.list_notes(city="北京")} == {n1["id"]})
ok("按来源过滤", {n["id"] for n in notes_store.list_notes(source="douyin")} == {n2["id"]})
ok("关键词命中正文", {n["id"] for n in notes_store.list_notes(keyword="火锅")} == {n2["id"]})
ok("关键词命中标题", {n["id"] for n in notes_store.list_notes(keyword="胡同")} == {n1["id"]})
ok("关键词命中标签", {n["id"] for n in notes_store.list_notes(keyword="咖啡")} == {n1["id"]})
ok("关键词无命中返回空", notes_store.list_notes(keyword="不存在的词xyz") == [])
ok("limit 生效", len(notes_store.list_notes(limit=1)) == 1)
ok("limit 被钳制在 1..500", len(notes_store.list_notes(limit=0)) >= 1)

# ---- 分页 / 计数 / 城市聚合（前端内容库列表依赖这些）----
ok("count_notes 与列表总数一致", notes_store.count_notes() == 4, str(notes_store.count_notes()))
ok("count_notes 跟随城市过滤", notes_store.count_notes(city="北京") == 1)
ok("count_notes 跟随来源过滤", notes_store.count_notes(source="douyin") == 1)
ok("count_notes 跟随关键词过滤", notes_store.count_notes(keyword="火锅") == 1)
_p1 = notes_store.list_notes(limit=2, offset=0)
_p2 = notes_store.list_notes(limit=2, offset=2)
ok("offset 分页生效（两页各 2 条）", len(_p1) == 2 and len(_p2) == 2, f"{len(_p1)}/{len(_p2)}")
ok("两页结果无重叠（分页不重复不漏项）", not ({x["id"] for x in _p1} & {x["id"] for x in _p2}))
ok("offset 超出范围返回空", notes_store.list_notes(limit=2, offset=99) == [])
ok(
    "负 offset 被钳制为 0",
    [x["id"] for x in notes_store.list_notes(limit=2, offset=-5)]
    == [x["id"] for x in notes_store.list_notes(limit=2, offset=0)],
)

_cities = {c["city"]: c["count"] for c in notes_store.list_cities()}
ok("城市聚合含北京/重庆且计数正确", _cities.get("北京") == 1 and _cities.get("重庆") == 1, str(_cities))
ok("城市聚合不包含空城市", "" not in _cities, str(_cities))

# ---- 编辑（PUT）：只改传入字段，其余保持原值 ----
_tmp = notes_store.add_note("manual", "待编辑", "原始正文", city="成都", tags="旧标签")
_u = notes_store.update_note(_tmp["id"], title="已改标题", city="西安")
ok("编辑可改标题与城市", _u["title"] == "已改标题" and _u["city"] == "西安", str(_u))
ok("编辑未传的字段保持原值", _u["content"] == "原始正文" and _u["tags"] == "旧标签", str(_u))
ok("编辑非法来源归一为 other", notes_store.update_note(_tmp["id"], source="weibo")["source"] == "other")
ok("编辑不存在的内容返回 None", notes_store.update_note("no-such", title="x") is None)
ok("编辑成空正文被拒绝", _raises(lambda: notes_store.update_note(_tmp["id"], content="   ")))
ok("编辑超长正文被拒绝", _raises(lambda: notes_store.update_note(_tmp["id"], content="x" * 20001)))
ok("清理临时内容", notes_store.delete_note(_tmp["id"]) is True)
ok("清理后总量回到 4", notes_store.note_stats()["total"] == 4)

ns = notes_store.note_stats()
ok("内容库总量正确", ns["total"] == 4, str(ns))
ok(
    "按来源分布正确",
    ns["by_source"].get("小红书") == 1 and ns["by_source"].get("抖音") == 1,
    str(ns["by_source"]),
)
ok("覆盖城市数正确（仅统计非空）", ns["city_count"] == 2, str(ns["city_count"]))
ok(
    "概览里带城市明细（前端一次请求即可渲染筛选下拉）",
    {c["city"] for c in ns["cities"]} == {"北京", "重庆"},
    str(ns["cities"]),
)

ok("详情可查", notes_store.get_note(n1["id"])["title"] == "北京胡同咖啡地图")
ok("不存在的详情返回 None", notes_store.get_note("no-such") is None)

# 导出到知识库
exp = notes_store.export_to_kb()
ok("导出按城市分组（北京/重庆/未分类）", exp["files"] == 3, str(exp))
ok("导出条目数与库内一致", exp["notes"] == 4, str(exp))
files = sorted(p.name for p in _KB.glob("外部攻略-*.md"))
ok(
    "知识库文件已生成（按城市各一个）",
    set(files) == {"外部攻略-北京.md", "外部攻略-重庆.md", "外部攻略-未分类.md"},
    str(files),
)
body = (_KB / "外部攻略-北京.md").read_text(encoding="utf-8")
ok("导出内容含标题", "北京胡同咖啡地图" in body)
ok("导出内容含来源标注", "来源：小红书" in body)
ok("导出内容含原文链接", "https://example.com/a" in body)
ok("导出内容含正文", "南锣鼓巷" in body)

ok("删除内容成功", notes_store.delete_note(n3["id"]) is True)
ok("删除不存在的内容返回 False", notes_store.delete_note("no-such") is False)
ok("删除后总量减少", notes_store.note_stats()["total"] == 3)
exp2 = notes_store.export_to_kb()
# 未分类里还有那条 weibo 内容，所以文件数仍是 3；但被删掉的 n3 不应再出现在导出结果里
ok("重新导出条目数与当前库一致", exp2["notes"] == 3, str(exp2))
uncat = (_KB / "外部攻略-未分类.md").read_text(encoding="utf-8")
ok("被删除的内容已从导出文件中消失", "未分类随笔" not in uncat)
ok("未被删除的同城内容仍在导出文件中", "微博来的内容" in uncat)
ok(
    "不误删用户自己上传的知识库文档",
    (
        lambda: (
            (_KB / "用户自己传的.md").write_text("x", encoding="utf-8")
            or notes_store.export_to_kb()
            or (_KB / "用户自己传的.md").exists()
        )
    )(),
)

# ============================================================ 7. API 层接线

# 给 alice 造一个属于她自己的会话，用来验证「会话历史」接口的归属校验
store.get_or_create_session("sess-ALICE")
store.set_session_user("sess-ALICE", "alice")
store.append_message("sess-ALICE", "user", "帮我规划成都三日游")
store.append_message("sess-ALICE", "assistant", "成都三天可以这样安排……")

from fastapi.testclient import TestClient

from app.main import app

with TestClient(app) as c:

    def _login(u, p):
        r = c.post("/api/auth/login", json={"username": u, "password": p})
        return r.json().get("token", "") if r.status_code == 200 else ""

    admin_h = {"Authorization": "Bearer " + _login("admin", "admin123")}
    user_h = {"Authorization": "Bearer " + _login("alice", "newpw123")}
    anon_h = {}

    ok("内容库：匿名访问 401", c.get("/api/notes").status_code == 401)
    r = c.get("/api/notes", headers=user_h)
    ok(
        "内容库：登录用户可读",
        r.status_code == 200 and len(r.json()) == 3,
        f"{r.status_code} n={len(r.json()) if r.status_code == 200 else '-'}",
    )
    r = c.get("/api/notes/stats", headers=user_h)
    ok("内容库：概览可读", r.status_code == 200 and r.json()["total"] == 3)
    r = c.get("/api/notes", params={"city": "北京"}, headers=user_h)
    ok("内容库：按城市过滤接口可用", r.status_code == 200 and len(r.json()) == 1)

    # 分页总数走 X-Total-Count 响应头（返回体保持数组，接口向后兼容）
    r = c.get("/api/notes", headers=user_h)
    ok(
        "内容库：列表带 X-Total-Count 响应头",
        r.headers.get("x-total-count") == "3",
        str(r.headers.get("x-total-count")),
    )
    r = c.get("/api/notes", params={"city": "北京"}, headers=user_h)
    ok(
        "内容库：X-Total-Count 跟随过滤条件",
        r.headers.get("x-total-count") == "1",
        str(r.headers.get("x-total-count")),
    )
    r = c.get("/api/notes", params={"limit": 1, "offset": 1}, headers=user_h)
    ok("内容库：limit/offset 分页可用", r.status_code == 200 and len(r.json()) == 1, f"{r.status_code}")
    r = c.get("/api/notes/stats", headers=user_h)
    ok(
        "内容库：概览返回城市明细",
        r.status_code == 200 and isinstance(r.json().get("cities"), list),
        r.text[:120],
    )

    ok(
        "内容库：普通用户不能新增",
        c.post("/api/notes", headers=user_h, json={"source": "manual", "content": "x"}).status_code == 403,
    )
    r = c.post(
        "/api/notes",
        headers=admin_h,
        json={
            "source": "xiaohongshu",
            "title": "接口写入",
            "content": "通过 API 写入的内容",
            "city": "上海",
            "tags": "接口",
        },
    )
    ok(
        "内容库：管理员可新增",
        r.status_code == 200 and r.json()["title"] == "接口写入",
        f"{r.status_code} {r.text[:120]}",
    )
    nid = r.json()["id"] if r.status_code == 200 else ""

    r = c.post("/api/notes", headers=admin_h, json={"source": "manual", "content": "   "})
    ok("内容库：空内容返回 400", r.status_code == 400, f"{r.status_code}")

    r = c.post("/api/notes", headers=admin_h, json={"source": "manual", "content": "x" * 20001})
    ok("内容库：超长内容返回 422/400", r.status_code in (400, 422), f"{r.status_code}")

    ok("内容库：详情可读", c.get(f"/api/notes/{nid}", headers=user_h).status_code == 200)
    ok("内容库：不存在的详情 404", c.get("/api/notes/no-such", headers=user_h).status_code == 404)
    ok("内容库：普通用户不能删除", c.delete(f"/api/notes/{nid}", headers=user_h).status_code == 403)
    ok("内容库：管理员可删除", c.delete(f"/api/notes/{nid}", headers=admin_h).status_code == 200)
    ok("内容库：删除后 404", c.get(f"/api/notes/{nid}", headers=user_h).status_code == 404)

    # ---- 编辑（PUT）：仅管理员，且只改传入字段 ----
    r = c.post(
        "/api/notes",
        headers=admin_h,
        json={"source": "manual", "title": "待编辑", "content": "原始正文", "city": "成都"},
    )
    eid = r.json()["id"] if r.status_code == 200 else ""
    ok("内容库：编辑前新建成功", bool(eid), f"{r.status_code} {r.text[:100]}")
    ok(
        "内容库：普通用户不能编辑",
        c.put(f"/api/notes/{eid}", headers=user_h, json={"title": "x"}).status_code == 403,
    )
    r = c.put(f"/api/notes/{eid}", headers=admin_h, json={"title": "改后标题", "tags": "新标签"})
    ok(
        "内容库：管理员可编辑",
        r.status_code == 200 and r.json()["title"] == "改后标题" and r.json()["tags"] == "新标签",
        f"{r.status_code} {r.text[:140]}",
    )
    ok("内容库：编辑保留未传字段", r.json()["content"] == "原始正文")
    ok(
        "内容库：编辑不存在的内容 404",
        c.put("/api/notes/no-such", headers=admin_h, json={"title": "x"}).status_code == 404,
    )
    ok(
        "内容库：编辑成空正文返回 400",
        c.put(f"/api/notes/{eid}", headers=admin_h, json={"content": "   "}).status_code == 400,
    )
    ok("内容库：编辑后清理成功", c.delete(f"/api/notes/{eid}", headers=admin_h).status_code == 200)

    ok("内容库：匿名不能看概览", c.get("/api/notes/stats", headers=anon_h).status_code == 401)

    # 会话历史接口也应读得到 SQLite 里的数据
    r = c.get("/api/chat/history/sess-ALICE", headers=user_h)
    ok(
        "会话历史接口可读 SQLite 数据",
        r.status_code == 200 and len(r.json()["messages"]) == 2,
        f"{r.status_code}",
    )
    r = c.get("/api/chat/history/sess-A", headers=user_h)
    ok("会话历史接口拒绝读取他人会话", r.status_code == 404, f"{r.status_code}")

    r = c.get("/api/chat/sessions", headers=user_h)
    ok(
        "我的会话列表只含自己的会话",
        r.status_code == 200 and {i["id"] for i in r.json()} == {"sess-ALICE"},
        f"{r.status_code}",
    )

    r = c.get("/api/admin/stats", headers=admin_h)
    ok("运营统计接口可读", r.status_code == 200 and r.json()["total_messages"] >= 9, f"{r.status_code}")

print("\n" + "=" * 60)
print(f"通过 {PASS} 项，失败 {FAIL} 项")
sys.exit(1 if FAIL else 0)
