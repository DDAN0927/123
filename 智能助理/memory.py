# -*- coding: utf-8 -*-
import os

os.environ["TOKENIZERS_PARALLELISM"] = "false"

_embeddings = None
_embeddings_failed = False
_vectordb = None


def get_embeddings():
    global _embeddings, _embeddings_failed
    if _embeddings is not None:
        return _embeddings
    if _embeddings_failed:
        return None

    api_key = os.getenv("OPENAI_API_KEY", "")
    base_url = os.getenv("OPENAI_BASE_URL", "")

    if api_key and base_url:
        try:
            from langchain_openai import OpenAIEmbeddings
            _embeddings = OpenAIEmbeddings(
                model="text-embedding-v3",
                openai_api_key=api_key,
                openai_api_base=base_url,
            )
            print(f"Embeddings: 使用 OpenAI API ({base_url})")
            return _embeddings
        except Exception as e:
            print(f"Warning: OpenAI Embeddings 加载失败: {e}")

    if api_key:
        try:
            from langchain_openai import OpenAIEmbeddings
            _embeddings = OpenAIEmbeddings(
                model="text-embedding-ada-002",
                openai_api_key=api_key,
            )
            print("Embeddings: 使用 OpenAI API (官方)")
            return _embeddings
        except Exception as e:
            print(f"Warning: OpenAI Embeddings (官方) 加载失败: {e}")

    try:
        os.environ["HF_ENDPOINT"] = os.getenv("HF_ENDPOINT", "https://hf-mirror.com")
        from langchain_community.embeddings import HuggingFaceEmbeddings
        _embeddings = HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2",
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )
        print("Embeddings: 使用本地 HuggingFace 模型")
        return _embeddings
    except Exception as e:
        print(f"Warning: HuggingFace Embeddings 加载失败: {e}")

    _embeddings_failed = True
    return None


def get_vectordb():
    global _vectordb
    if _vectordb is not None:
        return _vectordb
    embeddings = get_embeddings()
    if embeddings is None:
        return None
    try:
        from langchain_chroma import Chroma
        _vectordb = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
    except Exception as e:
        print(f"Warning: Failed to load vectordb: {e}")
        return None
    return _vectordb


def init_knowledge_base(file_path):
    db = get_vectordb()
    if not db:
        print("Failed to initialize knowledge base: vectordb not available")
        return
    from langchain_community.document_loaders import TextLoader
    from langchain_text_splitters import CharacterTextSplitter
    loader = TextLoader(file_path, encoding='utf-8')
    docs = loader.load()
    splitter = CharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_documents(docs)
    db.add_documents(chunks)