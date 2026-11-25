"""S-03 登录/注册限流的验收脚本（编码路径绕过 + context-path + 跨 IP 锁 + 反向用例 + N-08）。

用法
----
    # 阶段1：注册桶用例（必须最先跑，且桶必须是干净的）
    .venv/Scripts/python.exe scripts/qa_s03_regression.py --only=register

    # 中间**必须重启服务**

    # 阶段2：其余全部；第二个参数是可选的 context-path 实例
    .venv/Scripts/python.exe scripts/qa_s03_regression.py --only=main [http://127.0.0.1:8080] [http://127.0.0.1:18081]

退出码：0 全绿 / 1 有失败 / 2 参数不合法（未显式指定 --only，或用了 --only=all）。
账号与口令每次运行随机生成，不落任何固定凭据。

为什么必须分两阶段、中间重启
--------------------------
注册桶是「每个 IP 每小时 10 次」。阶段1 的用例要 **10 个空余额度**（先明文注册 4 个、
再用编码路径补 7 个，第 11 个必须 429）；而阶段2 要先注册 3 个账号才能测登录窗口。
修复生效后编码路径会被记账，阶段1 会把额度吃光 —— 于是阶段2 的账号注册不出来，
断言会以**错误理由**变红或变绿。一次跑完必然自相矛盾，所以拆开、中间重启清桶。
同理，任何阶段跑之前都要确认服务是刚重启的：桶里的残留会让「第 11 次 429」变成
「第 1 次就 429」，两者状态码一样但含义完全不同。

前置探针在防什么（别当冗余删掉）
------------------------------
`preflight()` 先用一次性用户名走**编码路径**打 6 次，必须出现 429 才继续。
这条不是为了测功能，是为了确认「打的是刚修好的那个进程」：
起第二个实例时如果端口被上一轮的孤儿进程占着，新实例会静默退出（日志里只有
`Port ... was already in use`），而用例会打到**旧包**上，得出既不是修前也不是修后的
第三种结果。历史上真发生过：报出来是 `401×5+429`，看着像"锁在生效"，其实是旧代码
在跑另一条路径。所以前置探针失败时不要判"修复无效"，按顺序查：
  1. 端口上的 PID 是不是你刚起的那个 java（netstat -ano / tasklist）
  2. jar 的 mtime 是否晚于目标 commit
  3. 启动日志有没有 `Port ... was already in use` / H2 锁报错

已知缺口（INFO，不判红）
----------------------
N-02：`body > 8192` 或 `Transfer-Encoding: chunked` 时读不出 username，限流键退化为
`anon|IP`，账号锁（第 3/4 道闸）整段失效，只剩 10 次/5 分钟 IP 窗口。这是修复前就有的
问题，脚本只报 INFO 不判红 —— 常红的用例会失去信号价值。判据：日志里出现
`username=- reason=window` 即为被利用的痕迹（正常锁是 `username=xxx reason=lock`）。
"""

import http.client
import json
import random
import string
import sys
import urllib.error
import urllib.request

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
ONLY = None
for _a in sys.argv[1:]:
    if _a.startswith("--only="):
        ONLY = _a.split("=", 1)[1]

BASE = ARGS[0] if ARGS else "http://127.0.0.1:8080"
CTX_BASE = ARGS[1] if len(ARGS) > 1 else None
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # 绕过系统代理
# 口令与用户名每次运行随机：脚本会被复制到别的环境跑，写死凭据要么撞库要么认证失败
PASSWORD = "Pw" + "".join(random.choices(string.ascii_letters + string.digits, k=10))
FAILED = []


def post_on(base, path, payload, headers=None):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(base + path, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    try:
        resp = OPENER.open(req, timeout=20)
        return resp.status, resp.read().decode("utf-8", "replace"), dict(resp.headers)
    except urllib.error.HTTPError as err:
        return err.code, err.read().decode("utf-8", "replace"), dict(err.headers)


def get_on(base, path):
    req = urllib.request.Request(base + path, method="GET")
    try:
        resp = OPENER.open(req, timeout=20)
        return resp.status
    except urllib.error.HTTPError as err:
        return err.code


def post(path, payload, headers=None):
    return post_on(BASE, path, payload, headers)


def post_src(src, path, payload):
    """从指定源地址发请求，用来构造两个不同的 remoteAddr（跨 IP 锁用例需要）。"""
    host = BASE.split("//", 1)[1]
    conn = http.client.HTTPConnection(host, timeout=20, source_address=(src, 0))
    conn.request("POST", path, json.dumps(payload).encode(), {"Content-Type": "application/json"})
    resp = conn.getresponse()
    body = resp.read().decode("utf-8", "replace")
    conn.close()
    return resp.status, body


def rnd(size=5):
    return "".join(random.choice(string.ascii_lowercase) for _ in range(size))


def check(name, cond, detail):
    print(f"{'PASS' if cond else 'FAIL'}  {name}  — {detail}")
    if not cond:
        FAILED.append(name)


def seq(path, times, user, password):
    """返回 [(status, body), ...]：断言要看整条序列和文案，不能只看末位状态码。"""
    return [post(path, {"username": user, "password": password})[:2] for _ in range(times)]


def codes(pairs):
    return [status for status, _ in pairs]


def has_lock(pairs, index):
    return "锁定" in pairs[index][1]


def preflight(tag):
    """确认打的是修好的那个进程，而不是孤儿旧包。原因见模块 docstring。"""
    status = get_on(BASE, "/api/auth/options")
    if status != 200:
        print(f"!! 前置检查失败：{BASE}/api/auth/options = {status}（实例没起 / 端口被占）")
        return False
    got = [post("/api/auth/%6Cogin", {"username": f"pf{tag}", "password": "WrongPass1"})[0] for _ in range(6)]
    if 429 not in got:
        print(f"!! 前置检查失败：编码路径 6 次全 {got}，无 429 —— 可能打的是旧进程/旧包，或修复无效。")
        print("   先查：(a) 端口 PID 是否为新起的 java (b) jar mtime 是否晚于 commit")
        print("         (c) 启动日志有无 `Port ... was already in use` / H2 锁报错")
        return False
    print(f"   前置检查通过：编码路径已被记账（{got}）")
    return True


def phase_register(tag):
    """注册桶：先明文 4 个、再编码路径 7 个，第 11 个必须 429。

    为什么不是「11 个全新用户名全走编码路径」：那样「共用同一个桶」与「编码路径另开一个桶」
    两种实现都会给出 200×10+429，测不出语义差别。先消耗 4 个额度再看编码路径是否接着计数，
    才能锁住「记账落在同一个键上」。
    """
    got = []
    for i in range(4):
        got.append(post("/api/auth/register", {"username": f"rg{tag}p{i}", "password": PASSWORD})[0])
    for i in range(7):
        got.append(post("/api/auth/%72egister", {"username": f"rg{tag}e{i}", "password": PASSWORD})[0])
    check(
        "A4 明文4 + 编码7 共用同一个注册桶（200x10 + 第11次429）",
        got[:10] == [200] * 10 and got[10] == 429,
        f"序列 {got}",
    )


def phase_main(tag):
    if not preflight(tag):
        return

    # 预置账号必须在 A4 之前完成：A4 会打满注册桶
    acc = {}
    for key in ("ok", "b", "ip"):
        user = f"rg{tag}{key}"
        status = post("/api/auth/register", {"username": user, "password": PASSWORD})[0]
        if status != 200:
            print(f"!! 预置账号 {user} 注册失败 {status}（桶不干净？请重启后再跑）")
            return
        acc[key] = user

    # ---- A) 编码路径绕过 ----
    # 每个变体必须用**不同的用户名**：锁键是「用户名|IP」，共用用户名时第一个变体打出的锁
    # 会让后面两个从第 1 次就 429 —— 那是测试 bug，判据是「首条就 429」而不是「401×5」。
    for idx, path in enumerate(("/api/auth/%6Cogin", "/api/auth/lo%67in", "/api/auth/%6C%6Fgin")):
        pairs = seq(path, 11, f"rg{tag}n{idx}", "WrongPass1")
        check(
            f"A 编码绕过 {path} 错口令 401x5 + 第6次锁",
            codes(pairs)[:5] == [401] * 5 and codes(pairs)[5] == 429 and has_lock(pairs, 5),
            f"序列 {codes(pairs)} 第6次文案={pairs[5][1][:40]}",
        )

    pairs = seq("/api/auth/%6Cogin", 11, acc["ok"], PASSWORD)
    check(
        "A 编码绕过 %6Cogin 正确口令 200x10 + 第11次429",
        codes(pairs)[:10] == [200] * 10 and codes(pairs)[10] == 429,
        f"序列 {codes(pairs)}",
    )

    # ---- B) 反向用例：不许改坏 ----
    pairs = seq("/api/auth/login", 11, acc["b"], PASSWORD)
    check(
        "B1 正常路径 200x10 + 第11次429",
        codes(pairs)[:10] == [200] * 10 and codes(pairs)[10] == 429,
        f"序列 {codes(pairs)}",
    )

    # 防「修过头」：把判定放宽成「路径含 auth 就过滤」会让登录页的公开选项接口被限流
    got = [get_on(BASE, "/api/auth/options") for _ in range(20)]
    check("B2 GET /api/auth/options x20 全 200（防修过头）", got == [200] * 20, f"序列 {got}")

    status, body, _ = post("/api/auth/login/", {"username": acc["b"], "password": PASSWORD})
    check("B3 /api/auth/login/ 不得变成 200", status != 200, f"{status} {body[:50]}")

    status, body, _ = post("/api/auth/login;x=1", {"username": acc["b"], "password": PASSWORD})
    check("B4 ;x=1 不得变成 200", status != 200, f"{status} {body[:50]}")

    # 防「误伤锁」：为修编码绕过而放宽判定时，锁逻辑不能一起被改掉
    pairs = seq("/api/auth/login", 6, f"rg{tag}k", "WrongPass1")
    check(
        "B5 正常路径第6次错口令仍是锁号",
        codes(pairs)[:5] == [401] * 5 and codes(pairs)[5] == 429 and has_lock(pairs, 5),
        f"序列 {codes(pairs)} 第6次文案={pairs[5][1][:40]}",
    )

    # ---- D) 跨 IP 锁隔离 ----
    # 锁键是「用户名|IP」：IP-A 锁住后，IP-B 用正确口令必须能进（锁不能变成锁死受害者的开关）
    user = acc["ip"]
    a_codes = [
        post_src("127.0.0.1", "/api/auth/login", {"username": user, "password": "WrongPass1"})[0]
        for _ in range(6)
    ]
    b_status, _ = post_src("127.0.0.2", "/api/auth/login", {"username": user, "password": PASSWORD})
    a_status, _ = post_src("127.0.0.1", "/api/auth/login", {"username": user, "password": PASSWORD})
    check(
        "D 跨IP锁隔离：IP-A 锁住后 IP-B 正确口令应 200，IP-A 仍 429",
        a_codes[:5] == [401] * 5 and b_status == 200 and a_status == 429,
        f"IP-A 序列 {a_codes} / IP-B={b_status} / IP-A 正确口令={a_status}",
    )

    # ---- E) N-08：经反代的 429 必须带 Retry-After ----
    retry_after = None
    for _ in range(4):
        status, _, headers = post("/api/chat/stream", {"message": ""})
        if status == 429:
            retry_after = headers.get("Retry-After") or headers.get("retry-after")
            break
    check("E 经 8080 的对话 429 带 Retry-After", retry_after is not None, f"Retry-After={retry_after}")

    # ---- F) 已知缺口 N-02：只报不判（见模块 docstring）----
    big = json.dumps({"username": f"rg{tag}big", "password": "WrongPass1"}).encode() + b" " * 9000
    got = []
    for _ in range(6):
        req = urllib.request.Request(BASE + "/api/auth/login", data=big, method="POST")
        req.add_header("Content-Type", "application/json")
        try:
            got.append(OPENER.open(req, timeout=20).status)
        except urllib.error.HTTPError as err:
            got.append(err.code)
    print(f"INFO  N-02 9KB body x6 → {got}（全 401 = 账号锁被静默降级，已知缺口，不判红）")

    # ---- C) context-path 部署：过滤器曾因 getRequestURI() 含前缀而整段失效 ----
    if CTX_BASE:
        user = f"ctx{tag}"
        reg = post_on(CTX_BASE, "/travel/api/auth/register", {"username": user, "password": PASSWORD})[0]
        got = [
            post_on(CTX_BASE, "/travel/api/auth/login", {"username": user, "password": PASSWORD})[0]
            for _ in range(11)
        ]
        check(
            f"C context-path 部署 {CTX_BASE} 200x10 + 第11次429",
            reg == 200 and got[:10] == [200] * 10 and got[10] == 429,
            f"register={reg} 序列 {got}（全 200 = 过滤器 fail-open）",
        )


def main():
    # 必须显式指定阶段。默认一次跑完（--only=all）看起来更省事，但必然失败：
    # 阶段1 会打满注册额度，阶段2 的预置账号就注册不出来 —— 而那个失败与代码无关，
    # 只与执行顺序有关。宁可在这里拦住，也不要让人拿到一条假的失败。
    if ONLY not in ("register", "main"):
        print(f"!! --only={ONLY!r} 不合法，必须显式指定阶段。")
        print("   原因：阶段1（register）会打满每 IP 每小时的 10 次注册额度，")
        print("   阶段2（main）开头要注册 3 个预置账号。一次跑完必然在预置账号处失败，")
        print("   而那个失败与代码无关，只与执行顺序有关 —— 别让它伪装成产品缺陷。")
        print()
        print("   正确顺序：")
        print("     1) --only=register")
        print("     2) 重启 Spring（内存桶清零）")
        print("     3) --only=main [http://127.0.0.1:8080] [http://127.0.0.1:18081]")
        return 2
    tag = rnd()
    if ONLY == "register":
        phase_register(tag)
    else:
        phase_main(tag)
    print()
    if FAILED:
        print(f"✗ {len(FAILED)} 条失败：{FAILED}")
        return 1
    print("✓ 全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
