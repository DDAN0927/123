#!/usr/bin/env bash
# 一键全量回归：后端 pytest + 接口冒烟 + 存储层 + 前端 jsdom 脚本
#
#   bash scripts/check_all.sh          # 全量
#   bash scripts/check_all.sh --fast   # 跳过最慢的 db_check / smoke
#
# 退出码：0 全部通过，1 有任一失败。CI 与本地用同一份入口。

set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

FAST=0
[ "${1:-}" = "--fast" ] && FAST=1

# ---------- 解析解释器 ----------
if [ -x ".venv/Scripts/python.exe" ]; then
  PY=".venv/Scripts/python.exe"
elif [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
else
  PY="$(command -v python3 || command -v python)"
fi

NODE_BIN="${NODE:-$(command -v node)}"
# jsdom 不在项目内 node_modules 时，回退到托管 workspace
if [ -z "${NODE_PATH:-}" ]; then
  for cand in "$PWD/node_modules" \
              "C:/Users/Administrator/.workbuddy-ai/binaries/node/workspace/node_modules"; do
    if [ -d "$cand/jsdom" ]; then export NODE_PATH="$cand"; break; fi
  done
fi

echo "python : $PY"
echo "node   : $NODE_BIN"
echo "NODE_PATH: ${NODE_PATH:-<未设置>}"
echo

# ---------- 用例表 ----------
NAMES=()
RESULTS=()
DETAILS=()
FAILED=0

run() {
  local name="$1"; shift
  printf '\033[36m▶ %s\033[0m\n' "$name"
  local out rc
  out="$("$@" 2>&1)"; rc=$?
  NAMES+=("$name")
  if [ $rc -eq 0 ]; then
    RESULTS+=("PASS")
    # 抓最后一行作为摘要（各脚本都会打印 "xx/xx 通过" 之类的收尾行）
    DETAILS+=("$(printf '%s\n' "$out" | tail -n 1)")
    printf '  \033[32m✓ 通过\033[0m  %s\n\n' "$(printf '%s\n' "$out" | tail -n 1)"
  else
    RESULTS+=("FAIL")
    DETAILS+=("exit=$rc")
    FAILED=$((FAILED + 1))
    printf '  \033[31m✗ 失败 (exit=%s)\033[0m\n' "$rc"
    printf '%s\n\n' "$out" | tail -n 40
  fi
}

run "后端单元/接口测试 (pytest)" "$PY" -m pytest -q
run "接口冒烟 (smoke)"           "$PY" scripts/smoke_test.py
if [ $FAST -eq 0 ]; then
  run "存储层 (db_check)"        "$PY" scripts/db_check.py
  # 检索质量：需要加载 BGE 模型（首次约 30s），故只在全量模式跑
  run "RAG 检索质量 (eval_rag)"  "$PY" scripts/eval_rag.py
fi
run "城市数据质量 (city_check)"   "$NODE_BIN" scripts/city_check.js
run "地图页 (map_check)"         "$NODE_BIN" scripts/map_check.js
run "Markdown 渲染 (md_render)"  "$NODE_BIN" scripts/md_render_check.js
run "前端 DOM (dom_check)"       "$NODE_BIN" scripts/dom_check.js
run "文案数字一致性 (copy_check)" "$NODE_BIN" scripts/copy_check.js

# ---------- 汇总 ----------
echo "══════════════════════════════════════════"
printf '%-32s %s\n' "用例" "结果"
echo "──────────────────────────────────────────"
for i in "${!NAMES[@]}"; do
  if [ "${RESULTS[$i]}" = "PASS" ]; then
    printf '%-32s \033[32m%s\033[0m\n' "${NAMES[$i]}" "PASS"
  else
    printf '%-32s \033[31m%s\033[0m\n' "${NAMES[$i]}" "FAIL"
  fi
done
echo "══════════════════════════════════════════"

if [ $FAILED -gt 0 ]; then
  echo "有 $FAILED 组用例失败"
  exit 1
fi
echo "全部通过"
