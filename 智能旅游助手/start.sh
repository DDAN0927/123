#!/bin/bash
# 启动脚本：FastAPI 对外提供官网静态站 + API
# 端口遵循 $PORT（云平台/发布沙箱注入），本地默认 7860
set -e

PORT="${PORT:-7860}"

# 持久化目录（云平台约定：$DATA_DIR / $KB_DIR 可指向持久化卷）
mkdir -p "$DATA_DIR" "$KB_DIR" 2>/dev/null || true
# 首次启动：把镜像内置攻略复制到持久化目录（同名已存在则跳过）
cp -n knowledge_base/*.md "$KB_DIR"/ 2>/dev/null || true

# 启动服务（含首次启动时的知识库索引自动构建）
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
