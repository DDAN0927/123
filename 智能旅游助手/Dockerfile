# 旅游智能助手 · ModelScope 创空间部署镜像
# 约定：uvicorn 直接监听 0.0.0.0:7860，同时提供官网静态站与 API（单进程单端口）
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_ENDPOINT=https://hf-mirror.com \
    DATA_DIR=/mnt/workspace/data \
    KB_DIR=/mnt/workspace/knowledge_base

WORKDIR /app

# 依赖：先装 CPU 版 torch（体积远小于 CUDA 版），再装其余依赖（国内镜像加速）
COPY requirements.txt .
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

# 预下载 BGE 向量模型到镜像层，避免首次请求时再等下载
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-zh-v1.5')"

# 应用代码与内置攻略库
COPY app ./app
COPY frontend ./frontend
COPY knowledge_base ./knowledge_base
COPY scripts ./scripts
COPY start.sh .

EXPOSE 7860
CMD ["bash", "start.sh"]
