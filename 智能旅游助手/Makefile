# 常用命令入口。Windows 没有 make 时，直接执行对应命令即可（见 README「开发」一节）。
.PHONY: help install dev run lint fmt test cov test-all eval-rag eval-e2e clean

PY ?= python
NODE ?= node

help:  ## 显示所有可用目标
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install:  ## 安装运行时依赖
	$(PY) -m pip install -r requirements.txt

dev:  ## 安装运行时 + 开发依赖
	$(PY) -m pip install -r requirements.txt -r requirements-dev.txt

run:  ## 本地启动（热重载）
	$(PY) -m uvicorn app.main:app --reload --port 7860

lint:  ## 静态检查（含格式检查，与 CI 一致）
	$(PY) -m ruff check app scripts tests
	$(PY) -m ruff format --check app scripts tests

fmt:  ## 自动修复 + 格式化
	$(PY) -m ruff check --fix app scripts tests
	$(PY) -m ruff format app scripts tests

test:  ## 后端单元/接口测试
	$(PY) -m pytest

cov:  ## 带覆盖率
	$(PY) -m pytest --cov=app --cov-report=term-missing

test-all: test  ## 全量回归（后端 pytest + 前端 jsdom 脚本，共 9 组）
	$(NODE) scripts/city_check.js
	$(NODE) scripts/map_check.js
	$(NODE) scripts/md_render_check.js
	$(NODE) scripts/dom_check.js
	$(NODE) scripts/copy_check.js
	$(PY) scripts/smoke_test.py
	$(PY) scripts/db_check.py
	$(PY) scripts/eval_rag.py

eval-rag:  ## RAG 检索质量（Recall@k / MRR / 城市命中率，离线）
	$(PY) scripts/eval_rag.py -v

eval-e2e:  ## 端到端回答质量（**会消耗真实 API 额度**，发版前手动跑）
	$(PY) scripts/eval_e2e.py

clean:  ## 清理测试与构建产物
	rm -rf .pytest_cache .ruff_cache htmlcov .coverage coverage.xml
	find . -type d -name __pycache__ -not -path './.venv/*' -exec rm -rf {} +
