# 可移植部署（不依赖任何 PaaS 的构建约定）。
# 构建上下文必须是**仓库根目录**：后端会用 ../index.html 同源提供前端，
# 所以只 COPY backend/ 会得到一个 404 的首页。
#
#   docker build -f backend/Dockerfile -t guanchao .
#   docker run --rm -p 8000:8000 guanchao
#   docker run --rm -p 8000:8000 -e ACCESS_TOKEN=xxx guanchao   # 开鉴权
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

# 先装依赖再拷源码：改代码不会让依赖层缓存失效
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY index.html ./index.html
COPY backend ./backend

EXPOSE 8000

# exec 形式 + sh -c 只为展开 ${PORT}；不用 --reload，不绑 127.0.0.1
CMD ["sh", "-c", "exec uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
