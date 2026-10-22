"""端到端回答质量评估：跑真实多 Agent 链路，检查「答得对不对」。

为什么需要它
------------
`scripts/eval_rag.py` 只回答「检索准不准」，`pytest` 只回答「代码有没有崩」。
两者都答不了用户真正关心的问题：**整条链路端到端跑下来，回答是不是对的**。
一个检索准确率 95% 的系统，完全可能因为汇总阶段截断、专家路由错、上下文
没传下去而给出一个缺斤少两的答案，而所有单测照样全绿。

这个脚本用一份人工标注的小样本，跑真实 LLM 链路，逐条断言：
* 回答非空，且命中预期城市
* 命中预期关键信息（门票/行程/开放时间等）
* 没有内部泄漏（「专家A说」「[planner]」、提示词围栏标记）
* 延迟在预算内

用法
----
    .venv/Scripts/python.exe scripts/eval_e2e.py            # 全量 6 条
    .venv/Scripts/python.exe scripts/eval_e2e.py --limit 2  # 只跑 2 条（省额度）
    .venv/Scripts/python.exe scripts/eval_e2e.py --mock     # 不调模型，只验链路连通
    .venv/Scripts/python.exe scripts/eval_e2e.py --json

成本提示：每条 query 会触发「路由 + 1~2 位专家 + 汇总」若干次 reasoner 调用，
单条约 5~15K tokens。默认 **不纳入 CI**（`check_all.sh` 不含本脚本），
只在发版前手动跑一次。

门禁：通过率 >= 0.8 且无内部泄漏，否则退出码 1。
"""

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# (问题, 必须命中的锚点之一, 必须覆盖的信息之一)
#
# 关于断言口径：早期版本要求回答里出现「城市名」，结果「故宫门票多少钱」被判失败
# —— 回答里写的是「故宫（紫禁城）」，用户本来就没问北京。城市硬约束是**检索层**
# 的规则（eval_rag.py 已经钉住），回答层应该只校验「有没有答到用户问的那个东西」。
CASES: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = [
    ("北京3天行程怎么安排", ("北京",), ("第1天", "第一天", "上午")),
    ("故宫门票多少钱，需要预约吗", ("故宫", "紫禁城"), ("元", "60", "预约")),
    ("成都和重庆的火锅有什么不同", ("火锅",), ("成都", "重庆", "牛油", "麻辣")),
    ("西安兵马俑开放时间是什么时候", ("兵马俑",), ("开放", "8", "点", "小时")),
    ("杭州西湖玩一天怎么安排", ("西湖",), ("断桥", "苏堤", "上午", "一天")),
    ("上海去苏州怎么走", ("苏州",), ("高铁", "动车", "交通", "分钟")),
]

# 内部实现泄漏：出现这些说明把系统提示词/内部协议暴露给了用户
LEAK_MARKERS = ("专家A说", "[planner]", "[food]", "<<<资料开始>>>", "知识库参考资料", "SYNTHESIZE_PROMPT")

LATENCY_BUDGET_S = 180.0
PASS_RATE_GATE = 0.8


def _make_sandbox() -> str:
    """建一个临时数据目录，并把现有 FAISS 索引复制进去。

    必须在 `import app.*` 之前调用：`settings` 是模块级单例，一旦导入就固定了
    `data_dir`。隔离数据目录是为了让评估不污染真实会话、消息与 token 统计
    （否则每跑一次评估，运营看板上的成本就虚增一笔）。
    索引只有几 MB，直接复制比重建快得多。
    """
    tmp = tempfile.mkdtemp(prefix="traveleval-")
    src_index = ROOT / "data" / "index"
    if src_index.is_dir():
        shutil.copytree(src_index, Path(tmp) / "index")
    os.environ["DATA_DIR"] = tmp
    return tmp


def _run_one(query: str) -> dict:
    from app.agents.graph import get_graph
    from app.store import get_stats

    usage_before = get_stats()["llm_usage"]
    state = {"query": query, "history": [], "outputs": {}, "trace": [], "steps": 0}

    answer, trace, errors = "", [], {}
    t0 = time.time()
    for update in get_graph().stream(state, stream_mode="updates"):
        for node, data in update.items():
            if not isinstance(data, dict):
                continue
            if node == "supervisor" and data.get("trace"):
                trace.append(data["trace"][-1])
            elif node == "synthesize" and data.get("final_answer") is not None:
                answer = data["final_answer"]
            elif data.get("errors"):
                errors.update(data["errors"])
    elapsed = time.time() - t0

    usage_after = get_stats()["llm_usage"]
    return {
        "answer": answer,
        "trace": trace,
        "errors": errors,
        "elapsed_s": round(elapsed, 1),
        "tokens": usage_after["total_tokens"] - usage_before["total_tokens"],
        "cost_cny": round(usage_after["estimated_cost_cny"] - usage_before["estimated_cost_cny"], 4),
        "agents": [t["agent"] for t in trace if t.get("agent") != "FINISH"],
    }


def _judge(
    case: tuple[str, tuple[str, ...], tuple[str, ...]], res: dict, mock: bool
) -> tuple[bool, list[str]]:
    _query, anchors, keywords = case
    answer = res["answer"] or ""
    problems = []

    if not answer.strip():
        problems.append("回答为空")
    leaks = [m for m in LEAK_MARKERS if m in answer]
    if leaks:
        problems.append(f"内部信息泄漏: {leaks}")

    if not mock:
        if not any(a in answer for a in anchors):
            problems.append(f"未答到用户问的对象 {anchors}")
        if not any(k in answer for k in keywords):
            problems.append(f"未覆盖关键信息 {keywords}")

    if res["elapsed_s"] > LATENCY_BUDGET_S:
        problems.append(f"耗时 {res['elapsed_s']}s 超预算 {LATENCY_BUDGET_S}s")

    return (not problems), problems


def main() -> int:
    ap = argparse.ArgumentParser(description="端到端回答质量评估")
    ap.add_argument("--limit", type=int, default=len(CASES), help="只跑前 N 条（省额度）")
    ap.add_argument("--mock", action="store_true", help="Mock 模式：不调真实模型，只验链路连通")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("-v", "--verbose", action="store_true", help="打印每条回答的开头")
    args = ap.parse_args()

    if args.mock:
        os.environ["LLM_PROVIDER"] = "mock"

    _make_sandbox()

    from app.rag import retriever

    if not retriever.index_ready():
        print("知识库索引不存在，请先运行 python scripts/build_kb.py")
        return 2

    cases = CASES[: max(1, args.limit)]
    results = []
    for case in cases:
        query = case[0]
        print(f"→ {query}", flush=True)
        try:
            res = _run_one(query)
        except Exception as e:  # 单条失败不应中断整轮评估
            res = {
                "answer": "",
                "trace": [],
                "errors": {"pipeline": str(e)},
                "elapsed_s": 0.0,
                "tokens": 0,
                "cost_cny": 0.0,
                "agents": [],
            }
        ok, problems = _judge(case, res, args.mock)
        results.append(
            {
                "query": query,
                "ok": ok,
                "problems": problems,
                "elapsed_s": res["elapsed_s"],
                "tokens": res["tokens"],
                "cost_cny": res["cost_cny"],
                "agents": res["agents"],
                "errors": res["errors"],
                "answer_head": (res["answer"] or "")[:160].replace("\n", " "),
            }
        )
        flag = "✓" if ok else "✗"
        print(
            f"  {flag} {res['elapsed_s']}s  {res['tokens']} tok  ¥{res['cost_cny']}  "
            f"agent={','.join(res['agents']) or '-'}"
        )
        if not ok:
            for p in problems:
                print(f"    · {p}")
        if args.verbose and res["answer"]:
            print(f"    {results[-1]['answer_head']}")

    passed = sum(1 for r in results if r["ok"])
    total_cost = round(sum(r["cost_cny"] for r in results), 4)
    summary = {
        "cases": len(results),
        "passed": passed,
        "pass_rate": round(passed / len(results), 3) if results else 0.0,
        "avg_latency_s": round(sum(r["elapsed_s"] for r in results) / max(1, len(results)), 1),
        "total_tokens": sum(r["tokens"] for r in results),
        "total_cost_cny": total_cost,
        "mock": args.mock,
    }

    if args.json:
        print(json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2))
    else:
        print()
        print(
            f"通过 {passed}/{len(results)} 条，平均耗时 {summary['avg_latency_s']}s，"
            f"共 {summary['total_tokens']} tokens，约 ¥{total_cost}"
        )

    if summary["pass_rate"] < PASS_RATE_GATE:
        print(f"\n✗ 通过率 {summary['pass_rate']:.0%} 低于门禁 {PASS_RATE_GATE:.0%}")
        return 1
    print(f"\n端到端评估通过：{summary['pass_rate']:.0%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
