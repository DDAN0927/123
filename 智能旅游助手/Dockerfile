# 旅游智能助手 · ModelScope 创空间部署镜像
#
# 两个进程，一个对外端口：
#   SpringBoot  $PORT（默认 7860）—— 唯一对外入口：认证 / 行程 / 记账 / 导出 / 静态站 / 反代
#   Python AI   127.0.0.1:7861     —— 只在内网：RAG 检索 + 多 Agent 对话
#
# jar 在构建阶段用 Maven 打出来，不把 55MB 二进制提交进仓库（每次构建都会变，diff 全废）。
# 没有 java / 没有 jar 时 start.sh 会退回单进程（只有 Python 对外），
# 所以「只拷 Python 的沙箱发布」那条路径不会被这套改动弄坏。

# ---------- 阶段 1：构建 SpringBoot 可执行 jar ----------
FROM maven:3.9-eclipse-temurin-17 AS build
WORKDIR /build

# 先只拷 pom 与 Maven 配置：依赖层单独缓存，改 Java 代码时不必重下依赖
COPY server/pom.xml ./
COPY server/docker-settings.xml /root/.m2/settings.xml
COPY server/src ./src

# 跳过测试编译：单测在本机与 CI 跑（scripts/server_check.sh），构建镜像时不必再跑一遍
RUN mvn -B -Dmaven.test.skip=true package

# ---------- 阶段 2：运行时 ----------
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_ENDPOINT=https://hf-mirror.com \
    DATA_DIR=/mnt/workspace/data \
    KB_DIR=/mnt/workspace/knowledge_base \
    JAVA_HOME=/opt/java/openjdk \
    AI_PORT=7861

ENV PATH="$JAVA_HOME/bin:$PATH"

WORKDIR /app

# 依赖：先装 CPU 版 torch（体积远小于 CUDA 版），再装其余依赖（国内镜像加速）
COPY requirements.txt .
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

# 预下载 BGE 向量模型到镜像层，避免首次请求时再等下载
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-zh-v1.5')"

# JDK 直接从构建阶段搬过来（同一个 temurin 基础镜像，路径 /opt/java/openjdk）
COPY --from=build /opt/java/openjdk /opt/java/openjdk

# 应用代码与内置攻略库
COPY app ./app
COPY frontend ./frontend
COPY knowledge_base ./knowledge_base
COPY scripts ./scripts
COPY start.sh .

# 预构建知识库索引，直接打进镜像。
#
# 为什么必须在构建期做：索引重建是**同步**跑在 lifespan 里的，建完才 bind 端口。
# 1042 块在 2 核容器上要 3~5 分钟，正好压在平台自己的启动超时上 —— 超时的表现是
# 「starting studio failed, please check the log.」，而平台不给日志，看起来像代码坏了。
# 镜像里带一份，start.sh 会把它装进 $DATA_DIR，冷启动几秒就 bind 端口。
#
# 为什么不提交进 git：它是 knowledge_base/ 的派生物，跟文档一起生成才不会失配
# （曾经就因为索引比文档旧，线上一直答旧攻略）。上面几层没变时这一层命中缓存，
# 不会拖慢日常构建；改了攻略库才会重算一次，那本来也该重算。
# KB_DIR 必须一起覆盖：运行阶段开头就把 KB_DIR 指到 /mnt/workspace（运行时卷），
# 构建期那个路径还不存在，只覆盖 DATA_DIR 会「知识库目录下没有文档」直接构建失败。
RUN DATA_DIR=/app/data KB_DIR=/app/knowledge_base \
    python -c "from app.rag.indexer import build_index; print('预构建索引:', build_index())"

# 业务主后端（放最后：改 Java 代码不会让上面几层缓存失效）
COPY --from=build /build/target/travel-server.jar ./server.jar

EXPOSE 7860
CMD ["bash", "start.sh"]
