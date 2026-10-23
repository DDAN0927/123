"""接口冒烟测试：验证鉴权、收藏隔离、会话归属与历史接口、限流与注册开关。

设计要点：
- 使用临时数据目录（DATA_DIR / KB_DIR 指向临时路径），不污染真实 data/；
- LLM_PROVIDER=mock，不调用真实大模型，保证离线、零成本、可重复；
- KB_DIR 保持为空，避免 lifespan 触发向量模型下载与索引构建；
- 限流窗口在用例内按需重置/调小，避免相互干扰。

运行：python scripts/smoke_test.py
"""

import os
import sys
import tempfile
from pathlib import Path

# ---- 必须在导入 app 之前设置环境变量（pydantic-settings 中环境变量优先于 .env）----
_TMP = Path(tempfile.mkdtemp(prefix="tc-smoke-"))
os.environ["DATA_DIR"] = str(_TMP / "data")
os.environ["KB_DIR"] = str(_TMP / "kb")
os.environ["LLM_PROVIDER"] = "mock"
# 管理员账号显式固定：否则会继承开发者本地 .env 里的 ADMIN_PASSWORD，测试随环境飘
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "admin123"
# 测试需要注册新账号；公网部署默认是关闭的，这里显式打开
os.environ["ALLOW_REGISTRATION"] = "true"
# 限流阈值调宽，避免干扰常规用例；限流专项用例会自行调小并重置窗口
os.environ["RATE_LIMIT_ENABLED"] = "true"
os.environ["RATE_LIMIT_ANONYMOUS_PER_MINUTE"] = "2"
os.environ["RATE_LIMIT_PER_MINUTE"] = "50"
os.environ["RATE_LIMIT_GLOBAL_PER_MINUTE"] = "100"
os.environ["AUTH_RATE_LIMIT_PER_MINUTE"] = "50"
(_TMP / "data").mkdir(parents=True, exist_ok=True)
(_TMP / "kb").mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from app.main import app

PASS, FAIL = [], []


def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'✅' if cond else '❌'} {name}{(' — ' + str(extra)) if extra else ''}")


def main():
    with TestClient(app) as c:
        # ---------- 基础 ----------
        r = c.get("/health")
        check("健康检查返回 ok", r.status_code == 200 and r.json().get("status") == "ok", r.text[:120])
        # 索引文件在 ≠ 检索可用：重型依赖延迟导入，torch 装失败时进程照样起得来
        h = r.json()
        check("健康检查区分 index_ready / rag_ready", "rag_ready" in h and "rag_error" in h, h)

        r = c.get("/api/agents")
        check("Agent 团队接口可用", r.status_code == 200 and len(r.json().get("experts", [])) == 5)

        # ---------- 知识库覆盖边界 ----------
        # 地图 355 城（只有坐标）与攻略库 6 城（有门票/开放时间）不是一回事，
        # 接口必须能把「哪些城市有资料」单独讲清楚，且无需登录即可查。
        r = c.get("/api/knowledge/coverage")
        cv = r.json() if r.status_code == 200 else {}
        check("知识库覆盖接口公开可用", r.status_code == 200 and isinstance(cv.get("cities"), list), r.text[:120])
        check(
            "覆盖接口带出地图规模（355 城 / 1558 景点）",
            cv.get("map_cities") == 355 and cv.get("map_spots") == 1558,
            cv,
        )

        from app.rag import coverage as cov_mod

        check("长白山不会被误判为吉林白山市", cov_mod.detect("长白山怎么去").asked == ())
        check("峨眉山不会被误判为四川眉山市", cov_mod.detect("峨眉山值得去吗").asked == ())
        check("马鞍山按最长匹配识别为马鞍山", cov_mod.detect("马鞍山有什么景点").asked == ("马鞍山",))
        check("无城市的问题不做城市判定", cov_mod.detect("三天行程怎么安排").asked == ())

        r = c.post("/api/chat", json={"message": "北京故宫门票多少钱"})
        body = r.json() if r.status_code == 200 else {}
        check(
            "对话响应带出城市覆盖判定",
            r.status_code == 200 and isinstance(body.get("coverage"), dict) and "asked" in body["coverage"],
            r.text[:120],
        )

        # ---------- 静态资源容错：非法/不存在的路径必须 404，不能 500 ----------
        for p in ["/a*b", "/%EF%BC%8C%60index_ready%3A", "/not-exist-page", "/x?y"]:
            r = c.get(p)
            check(f"非法路径 {p} 返回 404 而非 500", r.status_code == 404, r.status_code)

        # ---------- P0：知识库接口必须鉴权 ----------
        r = c.get("/api/knowledge/documents")
        check("知识库列表未登录返回 401", r.status_code == 401, r.status_code)
        r = c.post("/api/knowledge/rebuild")
        check("知识库重建未登录返回 401", r.status_code == 401, r.status_code)
        r = c.post("/api/knowledge/upload", files={"file": ("x.md", b"hello", "text/markdown")})
        check("知识库上传未登录返回 401", r.status_code == 401, r.status_code)

        # ---------- 管理员 ----------
        r = c.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        check("管理员登录成功", r.status_code == 200 and r.json().get("role") == "admin", r.text[:120])
        admin_h = {"Authorization": "Bearer " + r.json()["token"]}

        r = c.get("/api/admin/stats", headers=admin_h)
        check("管理员可读统计", r.status_code == 200)

        r = c.get("/api/knowledge/documents", headers=admin_h)
        check("管理员可读知识库列表", r.status_code == 200)

        r = c.post(
            "/api/knowledge/upload",
            headers=admin_h,
            files={"file": ("smoke.md", "# 测试\n内容".encode(), "text/markdown")},
        )
        check("管理员可上传知识库文档", r.status_code == 200, r.text[:120])
        r = c.get("/api/knowledge/documents", headers=admin_h)
        names = [d["name"] for d in r.json()]
        check("上传后文档出现在列表", "smoke.md" in names, names)
        r = c.delete("/api/knowledge/documents/smoke.md", headers=admin_h)
        check("管理员可删除知识库文档", r.status_code == 200)

        # ---------- 普通用户 A / B ----------
        ra = c.post("/api/auth/register", json={"username": "alice", "password": "pw123456"})
        rb = c.post("/api/auth/register", json={"username": "bob", "password": "pw123456"})
        check("注册 alice/bob 成功", ra.status_code == 200 and rb.status_code == 200)
        ha = {"Authorization": "Bearer " + ra.json()["token"]}
        hb = {"Authorization": "Bearer " + rb.json()["token"]}

        r = c.post("/api/auth/register", json={"username": "<script>x</script>", "password": "pw123456"})
        check("注册接口同样拦截非法用户名(422)", r.status_code == 422, r.status_code)

        # ---------- 鉴权头兼容：Authorization: Bearer 与 X-Auth-Token 都要认 ----------
        # 背景：部分平台的边缘 WAF（实测魔搭创空间 *.ms.show）会把**任何**带
        # Authorization: Bearer 的请求当成「SDK Token 直连」直接 403，与 token 内容
        # 无关，应用层根本收不到请求。前端因此改用 X-Auth-Token，后端必须两种都支持。
        tok_admin = admin_h["Authorization"][7:]
        tok_a = ha["Authorization"][7:]

        r = c.get("/api/auth/me", headers={"Authorization": "Bearer " + tok_admin})
        check("鉴权头 Bearer 可用", r.status_code == 200 and r.json()["username"] == "admin", r.text[:80])
        r = c.get("/api/auth/me", headers={"X-Auth-Token": tok_admin})
        check(
            "鉴权头 X-Auth-Token 可用", r.status_code == 200 and r.json()["username"] == "admin", r.text[:80]
        )
        r = c.get("/api/auth/me", headers={"X-Auth-Token": tok_admin, "Authorization": "Bearer " + tok_admin})
        check("两种鉴权头同时携带不冲突", r.status_code == 200, r.status_code)

        r = c.get("/api/auth/me", headers={"X-Auth-Token": "bogus"})
        check("X-Auth-Token 无效 token 返回 401", r.status_code == 401, r.status_code)
        r = c.get("/api/auth/me", headers={"Authorization": "Bearer bogus"})
        check("Bearer 无效 token 返回 401", r.status_code == 401, r.status_code)
        r = c.get("/api/auth/me", headers={"Authorization": "bogus"})
        check("Authorization 缺 Bearer 前缀返回 401", r.status_code == 401, r.status_code)
        r = c.get("/api/auth/me", headers={"Authorization": "Bearer "})
        check("Bearer 空 token 返回 401", r.status_code == 401, r.status_code)
        r = c.get("/api/auth/me")
        check("完全不带鉴权头返回 401", r.status_code == 401, r.status_code)

        r = c.get("/api/admin/stats", headers={"X-Auth-Token": tok_admin})
        check("管理员接口认 X-Auth-Token", r.status_code == 200, r.status_code)
        r = c.get("/api/favorites", headers={"X-Auth-Token": tok_a})
        check("收藏接口认 X-Auth-Token", r.status_code == 200, r.status_code)
        r = c.get("/api/admin/stats", headers={"X-Auth-Token": tok_a})
        check("X-Auth-Token 下普通用户仍被挡(403)", r.status_code == 403, r.status_code)

        r = c.post("/api/auth/logout", headers={"X-Auth-Token": tok_a})
        check("登出接口认 X-Auth-Token", r.status_code == 200, r.status_code)
        r = c.get("/api/auth/me", headers={"X-Auth-Token": tok_a})
        check("登出后 X-Auth-Token 立即失效", r.status_code == 401, r.status_code)
        # 重新登录，后续用例继续用 ha
        ra = c.post("/api/auth/login", json={"username": "alice", "password": "pw123456"})
        ha = {"Authorization": "Bearer " + ra.json()["token"]}
        check("重新登录成功（后续用例可继续）", ra.status_code == 200, ra.status_code)

        r = c.get("/api/admin/stats", headers=ha)
        check("普通用户访问管理接口返回 403", r.status_code == 403, r.status_code)
        r = c.get("/api/knowledge/documents", headers=ha)
        check("普通用户访问知识库返回 403", r.status_code == 403, r.status_code)

        # ---------- P1：收藏按用户隔离 ----------
        r = c.get("/api/favorites")
        check("收藏列表未登录返回 401", r.status_code == 401, r.status_code)

        r = c.post("/api/favorites", json={"title": "北京攻略", "content": "# 北京\n好玩"}, headers=ha)
        check("alice 可新增收藏", r.status_code == 200, r.text[:120])
        fid = r.json().get("id")

        ra_list = c.get("/api/favorites", headers=ha).json()["favorites"]
        rb_list = c.get("/api/favorites", headers=hb).json()["favorites"]
        check("alice 能看到自己的收藏", len(ra_list) == 1 and ra_list[0]["id"] == fid)
        check("bob 看不到 alice 的收藏", len(rb_list) == 0, rb_list)

        r = c.delete(f"/api/favorites/{fid}", headers=hb)
        check("bob 删除 alice 的收藏返回 404", r.status_code == 404, r.status_code)
        check("alice 的收藏未被越权删除", len(c.get("/api/favorites", headers=ha).json()["favorites"]) == 1)

        # ---------- 会话：归属与历史 ----------
        r = c.post("/api/chat", json={"message": "你好"}, headers=ha)
        check("mock 模式对话返回 200", r.status_code == 200, r.text[:120])
        sid = r.json().get("session_id")
        check("对话返回 session_id", bool(sid), sid)

        r = c.get("/api/chat/sessions", headers=ha)
        check(
            "alice 会话列表包含该会话",
            r.status_code == 200 and any(s["id"] == sid for s in r.json()),
            r.text[:150],
        )
        check("会话列表带标题", r.status_code == 200 and r.json()[0].get("title"))

        r = c.get(f"/api/chat/history/{sid}", headers=ha)
        check(
            "alice 可读自己的会话历史",
            r.status_code == 200 and len(r.json().get("messages", [])) >= 2,
            r.text[:150],
        )
        r = c.get(f"/api/chat/history/{sid}", headers=hb)
        check("bob 读取 alice 的会话返回 404", r.status_code == 404, r.status_code)
        r = c.get("/api/chat/sessions", headers=hb)
        check("bob 会话列表为空", r.json() == [], r.text[:120])

        # ---------- 管理端会话列表含 username（此前被 schema 吞掉）----------
        r = c.get("/api/admin/sessions", headers=admin_h)
        rows = r.json()
        check(
            "管理端会话列表含 username 字段",
            r.status_code == 200 and all("username" in x for x in rows) and rows,
            rows[:1],
        )
        check(
            "管理端会话能定位到 alice",
            any(x.get("username") == "alice" for x in rows),
            [x.get("username") for x in rows],
        )

        # ---------- 反馈 ----------
        r = c.post(
            "/api/chat/feedback", json={"session_id": sid, "message_index": 1, "rating": "like"}, headers=ha
        )
        check("点赞反馈可记录", r.status_code == 200, r.text[:120])
        r = c.post(
            "/api/chat/feedback", json={"session_id": sid, "message_index": 1, "rating": "bad"}, headers=ha
        )
        check("非法 rating 被拒绝(422)", r.status_code == 422, r.status_code)

        # ---------- 流式对话事件序列 ----------
        with c.stream("POST", "/api/chat/stream", json={"message": "你好"}, headers=ha) as resp:
            body = "".join(resp.iter_text())
        check("SSE 先下发 session 事件", '"type": "session"' in body, body[:160])
        check("SSE 含 answer 事件", '"type": "answer"' in body)
        check("SSE 含 done 事件", '"type": "done"' in body)

        # ---------- 登录页选项（前端据此隐藏注册入口）----------
        r = c.get("/api/auth/options")
        check(
            "/api/auth/options 暴露注册开关",
            r.status_code == 200 and r.json().get("allow_registration") is True,
            r.text[:120],
        )

        # ---------- 管理员开通账号（关闭开放注册后唯一的开号入口）----------
        r = c.post(
            "/api/admin/users",
            json={"username": "carol", "password": "pw123456", "role": "user"},
            headers=admin_h,
        )
        check("管理员可开通账号", r.status_code == 200 and r.json().get("username") == "carol", r.text[:120])
        r = c.post("/api/admin/users", json={"username": "carol", "password": "pw123456"}, headers=admin_h)
        check("重复用户名返回 400", r.status_code == 400, r.status_code)
        r = c.post("/api/admin/users", json={"username": "dave", "password": "pw123456"})
        check("未登录不能开通账号", r.status_code == 401, r.status_code)
        r = c.post("/api/admin/users", json={"username": "dave", "password": "pw123456"}, headers=ha)
        check("普通用户不能开通账号", r.status_code == 403, r.status_code)
        r = c.post("/api/admin/users", json={"username": "eve", "password": "123"}, headers=admin_h)
        check("密码过短被拒绝(422)", r.status_code == 422, r.status_code)
        r = c.post("/api/auth/login", json={"username": "carol", "password": "pw123456"})
        check("管理员开通的账号可登录", r.status_code == 200, r.text[:120])

        # ---------- 用户名字符白名单（服务端拦截，不依赖前端转义）----------
        # 用户名会渲染进导航栏和运营看板，<>"' 这类字符必须在入口就挡掉。
        for bad in ("<img src=x onerror=alert(1)>", 'a"b', "a'b", "a<b", "a>b", "a\\b"):
            r = c.post("/api/admin/users", json={"username": bad, "password": "pw123456"}, headers=admin_h)
            check(f"非法用户名被拒绝(422): {bad!r}", r.status_code == 422, r.status_code)
        # 合法字符应放行：中文 / 下划线 / 连字符 / 点 / @
        r = c.post(
            "/api/admin/users", json={"username": "旅_行-者.01@cn", "password": "pw123456"}, headers=admin_h
        )
        check("合法用户名（中文/符号）可开通", r.status_code == 200, r.text[:120])
        r = c.post("/api/admin/users", json={"username": "x" * 33, "password": "pw123456"}, headers=admin_h)
        check("用户名超长(33)被拒绝(422)", r.status_code == 422, r.status_code)

        # ---------- 关闭开放注册后，注册入口必须拒绝 ----------
        from app.config import settings as _settings

        _prev_allow = _settings.allow_registration
        _settings.allow_registration = False
        r = c.post("/api/auth/register", json={"username": "zzz", "password": "pw123456"})
        check("关闭开放注册后注册返回 403", r.status_code == 403, r.status_code)
        _settings.allow_registration = _prev_allow

        # ---------- 限流 ----------
        from app import ratelimit as rl

        # 1) 匿名单 IP 阈值
        rl._llm_anon.limit, rl._llm_global.limit = 2, 100
        rl._llm_anon.reset(), rl._llm_global.reset()
        codes = [
            c.post("/api/chat", json={"message": "你好"}, headers={"X-Forwarded-For": "9.9.9.9"}).status_code
            for _ in range(3)
        ]
        check("匿名同一 IP 超阈值返回 429", codes[:2] == [200, 200] and codes[2] == 429, codes)

        # 2) 全局硬上限：伪造 X-Forwarded-For 轮换 IP 也绕不过
        rl._llm_anon.limit, rl._llm_global.limit = 99, 3
        rl._llm_anon.reset(), rl._llm_global.reset()
        codes = [
            c.post(
                "/api/chat", json={"message": "你好"}, headers={"X-Forwarded-For": f"8.8.{i}.{i}"}
            ).status_code
            for i in range(4)
        ]
        check("全局硬上限生效（轮换 IP 也拦得住）", codes[:3] == [200, 200, 200] and codes[3] == 429, codes)

        # 3) 登录/注册防暴破
        rl._auth_ip.limit = 3
        rl._auth_ip.reset()
        codes = [
            c.post(
                "/api/auth/login",
                json={"username": "admin", "password": "wrong"},
                headers={"X-Forwarded-For": "7.7.7.7"},
            ).status_code
            for _ in range(4)
        ]
        check("登录失败尝试过多返回 429", codes[:3] == [401, 401, 401] and codes[3] == 429, codes)

        # 恢复宽松阈值，避免影响后续断言
        rl._llm_anon.limit, rl._llm_global.limit = 99, 100
        rl._llm_anon.reset(), rl._llm_global.reset(), rl._auth_ip.reset()

        # 4) 管理员可查看限流状态
        r = c.get("/api/admin/ratelimit", headers=admin_h)
        check("管理员可查看限流状态", r.status_code == 200 and "enabled" in r.json(), r.text[:120])
        r = c.get("/api/admin/ratelimit")
        check("限流状态未登录返回 401", r.status_code == 401, r.status_code)

        # ---------- 天气工具：降级数据必须覆盖所有支持的城市 ----------
        # 真实 open-meteo 不可用时会走 _query_mock，此前 _CITY_TEMP 只有 12 城，
        # 另外 8 城一断网就 KeyError，整个工具调用直接失败。
        from app.tools.weather import _CITY_COORD, _CITY_TEMP, _query_mock

        missing_temp = [k for k in _CITY_COORD if k not in _CITY_TEMP]
        check("天气降级表覆盖全部支持城市", not missing_temp, missing_temp)

        crashed = []
        for key in _CITY_COORD:
            try:
                txt = _query_mock(key, 3)
                if key not in txt or "℃" not in txt:
                    crashed.append(key + "(内容异常)")
            except Exception as e:
                crashed.append(f"{key}({type(e).__name__})")
        check("20 城降级天气都能正常生成", not crashed, crashed)

        from app.tools.weather import query_weather

        out = query_weather.invoke({"city": "哈尔滨", "days": 3})
        check("哈尔滨天气可查询（不再 KeyError）", "哈尔滨" in out and "℃" in out, out[:80])

    print("\n" + "=" * 60)
    print(f"通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
    if FAIL:
        print("失败项：" + "、".join(FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
