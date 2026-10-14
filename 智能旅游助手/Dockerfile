# 旅游智能助手 · ModelScope 创空间部署镜像
# 约定：对外服务必须监听 0.0.0.0:7860（FastAPI 后端走容器内部 8000）
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    HF_ENDPOINT=https://hf-mirror.com \
    API_URL=http://127.0.0.1:8000 \
    DATA_DIR=/mnt/workspace/data \
    KB_DIR=/mnt/workspace/knowledge_base

WORKDIR /app

# 依赖：先装 CPU 版 torch（体积小），再装其余依赖（国内镜像加速）
COPY requirements.txt .
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

# 预下载 BGE 向量模型到镜像层，避免运行时等待
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-zh-v1.5')"

# 应用代码与内置攻略库
COPY app ./app
COPY frontend ./frontend
COPY knowledge_base ./knowledge_base
COPY scripts ./scripts
COPY start.sh .

EXPOSE 7860
CMD ["bash", "start.sh"]
