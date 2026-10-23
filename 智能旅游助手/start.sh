#!/bin/bash
# 启动脚本：FastAPI 对外提供官网静态站 + API
# 端口遵循 $PORT（云平台/发布沙箱注入），本地默认 7860
set -e

PORT="${PORT:-7860}"

# 持久化目录（云平台约定：$DATA_DIR / $KB_DIR 可指向持久化卷）
mkdir -p "$DATA_DIR" "$KB_DIR" 2>/dev/null || true
# 把镜像内置攻略同步到持久化目录：**按内容比较**，不同才覆盖。
# 为什么不用 cp -n：已存在就跳过，会让镜像里的攻略更新永远进不了持久化卷 ——
#   卷上还是上一版正文，本地测试一切正常、线上一直答旧内容，极难发现。
# 为什么不用 cp -u：它比 mtime，而镜像层与卷的时钟来源不同，判不准。
# 管理员另存的文档名与内置的不同，不会被这段逻辑碰到。
for f in knowledge_base/*.md; do
  [ -e "$f" ] || continue
  dest="$KB_DIR/$(basename "$f")"
  if [ ! -f "$dest" ] || ! cmp -s "$f" "$dest"; then
    cp "$f" "$dest"
  fi
done

# 启动服务（含首次启动时的知识库索引自动构建）
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
