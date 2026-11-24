#!/bin/sh
# QA runner: 顺序执行给定探针,输出到 _qa_logs/<name>.log
cd "$(dirname "$0")" || exit 1
mkdir -p _qa_logs
for f in "$@"; do
  name=$(basename "$f" .js)
  echo "=== RUN $name ==="
  node "$f" > "_qa_logs/$name.log" 2>&1
  code=$?
  echo "$name exit=$code"
done
