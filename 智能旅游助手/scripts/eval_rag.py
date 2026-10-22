"""RAG 检索质量评估：Recall@k / MRR / 城市命中率

为什么需要这个脚本
------------------
「RAG 能跑通」和「RAG 检得准」是两件事。此前项目只有功能测试（接口返回 200、
有资料注入），没有任何指标能回答「检索到底准不准、改切分后是变好还是变差」。
这个脚本用一份人工标注的 query 集把检索质量钉成数字，并作为回归门禁。

用法
----
    .venv/Scripts/python.exe scripts/eval_rag.py            # 跑评估
    .venv/Scripts/python.exe scripts/eval_rag.py -v         # 打印每个 query 的命中详情
    .venv/Scripts/python.exe scripts/eval_rag.py --json     # 机器可读输出

指标
----
* Recall@1 / @3：top-k 里存在「标注的正确小节」的 query 占比
* MRR：正确小节排名的倒数均值（越接近 1 越好，衡量排序而不只是召回到）
* City@1：top-1 命中城市文档的占比（防止把「成都火锅」答成重庆）

门禁阈值（低于则退出码 1）：Recall@3 >= 0.90 且 MRR >= 0.75 且 City@1 >= 0.90
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# (query, 期望城市文档, 正确小节的关键词)
# 关键词语义：该词必须出现在命中块里，才算「检索到了正确的那一节」
CASES: list[tuple[str, str, str]] = [
    ("故宫门票多少钱", "北京.md", "故宫"),
    ("北京长城怎么去", "北京.md", "长城"),
    ("颐和园开放时间", "北京.md", "颐和园"),
    ("北京烤鸭哪家好吃", "北京.md", "烤鸭"),
    ("北京住宿住哪个区域方便", "北京.md", "住宿"),
    ("上海外滩夜景", "上海.md", "外滩"),
    ("上海迪士尼门票", "上海.md", "迪士尼"),
    ("上海本帮菜推荐", "上海.md", "本帮"),
    ("成都大熊猫基地几点去", "成都.md", "大熊猫"),
    ("成都必吃的火锅", "成都.md", "火锅"),
    ("成都宽窄巷子值得去吗", "成都.md", "宽窄巷子"),
    ("杭州西湖怎么玩", "杭州.md", "西湖"),
    ("杭州龙井茶去哪买", "杭州.md", "龙井"),
    ("西安兵马俑开放时间", "西安.md", "兵马俑"),
    ("西安回民街有什么好吃的", "西安.md", "回民街"),
    ("西安城墙骑行", "西安.md", "城墙"),
    ("重庆洪崖洞夜景", "重庆.md", "洪崖洞"),
    ("重庆火锅推荐", "重庆.md", "火锅"),
    ("重庆解放碑附近住哪", "重庆.md", "解放碑"),
    ("重庆三天怎么安排", "重庆.md", "行程"),
    # —— 以下为「难例」：专有名词、跨城干扰、城市硬约束 ——
    ("灵隐寺门票", "杭州.md", "灵隐寺"),
    ("西溪湿地怎么去", "杭州.md", "西溪湿地"),
    ("都江堰青城山一日游", "成都.md", "都江堰"),
    ("磁器口古镇有什么好玩的", "重庆.md", "磁器口"),
    ("长江索道要排多久", "重庆.md", "长江索道"),
    ("陕西历史博物馆怎么预约", "西安.md", "陕西历史博物馆"),
    ("华清宫值得去吗", "西安.md", "华清宫"),
    ("天坛公园门票", "北京.md", "天坛"),
    ("田子坊逛街", "上海.md", "田子坊"),
    ("李子坝轻轨穿楼", "重庆.md", "李子坝"),
    ("锦里古街晚上去", "成都.md", "锦里"),
    # 跨城查询：苏州不在知识库，但查询点名了上海，必须落回上海交通指南，
    # 而不是被「怎么走」带到北京的颐和园（这是修复前的真实表现）。
    ("上海去苏州怎么走", "上海.md", "交通"),
    # 同名美食干扰：两个城市都有「火锅」段落，必须按城市区分
    ("成都火锅和重庆火锅有什么不同", "成都.md", "火锅"),
]

RECALL_K = (1, 3)
THRESHOLDS = {"recall@3": 0.90, "mrr": 0.75, "city@1": 0.90}


def evaluate(verbose: bool = False) -> dict:
    from app.rag import retriever

    if not retriever.index_ready():
        print("知识库索引不存在，请先运行 python scripts/build_kb.py")
        raise SystemExit(2)

    top_k = max(RECALL_K)
    hits = dict.fromkeys(RECALL_K, 0)
    rr_sum = 0.0
    city_hit = 0
    details = []

    for query, want_doc, want_kw in CASES:
        results = retriever.search(query, top_k)
        rank = 0
        for i, r in enumerate(results, 1):
            if r["doc"] == want_doc and want_kw in r["text"]:
                rank = i
                break
        for k in RECALL_K:
            if rank and rank <= k:
                hits[k] += 1
        rr_sum += 1.0 / rank if rank else 0.0
        top1_city_ok = bool(results) and results[0]["doc"] == want_doc
        city_hit += 1 if top1_city_ok else 0
        details.append(
            {
                "query": query,
                "want": f"{want_doc}#{want_kw}",
                "rank": rank,
                "top1": results[0]["text"][:34].replace("\n", " ") if results else "(空)",
                "top1_city_ok": top1_city_ok,
            }
        )
        if verbose:
            flag = "✓" if rank == 1 else ("△" if rank else "✗")
            print(f"{flag} rank={rank or '-'}  {query}")
            if rank != 1:
                print(f"    want {want_doc}#{want_kw}  got {details[-1]['top1']}")

    n = len(CASES)
    metrics = {
        **{f"recall@{k}": hits[k] / n for k in RECALL_K},
        "mrr": rr_sum / n,
        "city@1": city_hit / n,
        "cases": n,
    }
    return {"metrics": metrics, "details": details}


def main() -> int:
    ap = argparse.ArgumentParser(description="RAG 检索质量评估")
    ap.add_argument("-v", "--verbose", action="store_true", help="打印每个 query 的命中详情")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出结果")
    args = ap.parse_args()

    report = evaluate(verbose=args.verbose)
    m = report["metrics"]

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print()
        print(f"{'指标':<12}{'值':>8}")
        print("-" * 20)
        for key in ("recall@1", "recall@3", "mrr", "city@1"):
            print(f"{key:<12}{m[key]:>8.3f}")

    failed = [k for k, th in THRESHOLDS.items() if m[k] < th]
    if failed:
        print()
        for k in failed:
            print(f"✗ {k} = {m[k]:.3f}，低于门禁 {THRESHOLDS[k]:.2f}")
        print(f"\nRAG 评估未通过：{len(failed)} 项指标低于阈值")
        return 1

    print(f"\nRAG 评估通过：{m['cases']} 条 query，Recall@3 {m['recall@3']:.0%}，MRR {m['mrr']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
