"""RAG 检索工具：普通函数（自动注入上下文）+ LangChain 工具（供 Agent 主动检索）"""
from langchain_core.tools import tool

from app.rag import retriever


def get_rag_context(query: str, top_k: int | None = None) -> str:
    """根据查询检索知识库，返回格式化参考资料；不可用时返回空提示"""
    try:
        results = retriever.search(query, top_k)
    except Exception as e:
        return f"(知识库暂不可用: {e})"
    if not results:
        return "(知识库中未检索到相关资料)"
    parts = []
    for i, r in enumerate(results, 1):
        parts.append(f"【资料{i}】(来源: {r['doc']}, 相似度 {r['score']:.2f})\n{r['text']}")
    return "\n\n".join(parts)


@tool
def search_knowledge(query: str) -> str:
    """搜索旅游知识库，获取景点、美食、行程、交通等攻略资料。query 为检索关键词，如"北京 故宫 门票"。"""
    return get_rag_context(query)
