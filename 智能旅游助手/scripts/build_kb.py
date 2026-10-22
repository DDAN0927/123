"""知识库构建脚本: python scripts/build_kb.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.rag.indexer import build_index


def main():
    print("开始构建知识库索引 ...")
    stats = build_index()
    print(f"完成: 文档 {stats['documents']} 篇, 文本块 {stats['chunks']} 个, 向量维度 {stats['dimension']}")


if __name__ == "__main__":
    main()
