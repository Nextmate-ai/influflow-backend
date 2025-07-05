# Influflow - Twitter Thread Generator
# 使用 uv 运行应用的 Makefile

.PHONY: help run-ui run-api run-langgraph install test test-quick-validation test-tweet-generate

# 默认目标：显示帮助信息
all: help

# 启动 Streamlit UI 界面
run-ui:
	uv run python start_ui.py

# 启动 FastAPI 后端服务器
run-api:
	uv run python start_api.py

# 安装项目依赖
install:
	uv sync

# 启动 LangGraph 开发服务器
run-langgraph:
	uv run uvx --refresh --from "langgraph-cli[inmem]" --with-editable . --python 3.11 langgraph dev --allow-blocking

# 运行所有测试
test:
	uv run python -m pytest test/ -v

# 运行推文生成单一测试
test-quick-validation:
	uv run python test/test_quick_validation.py

# 运行推文生成测试
test-tweet-generate:
	uv run python test/test_tweet_generate.py

# 显示帮助信息
help:
	@echo "Influflow - Twitter Thread Generator"
	@echo ""
	@echo "🚀 启动命令:"
	@echo "  run-ui              启动 Streamlit UI 界面"
	@echo "  run-api             启动 FastAPI 后端服务器"
	@echo "  run-langgraph       启动 LangGraph 开发服务器"
	@echo ""
	@echo "🧪 测试命令:"
	@echo "  test                运行所有测试"
	@echo "  test-quick-validation  运行推文生成单一测试"
	@echo "  test-tweet-generate 运行推文生成测试"
	@echo ""
	@echo "⚙️  环境管理:"
	@echo "  install             安装项目依赖"
	@echo "  help                显示此帮助信息"
	@echo ""
	@echo "💡 快速开始:"
	@echo "  make install            # 首次运行：安装依赖"
	@echo "  make dev                # 开发模式（推荐）"
	@echo "  make run-both           # 同时启动 UI 和 API"
	@echo "  make run-api            # 单独启动 API 服务器"
	@echo "  make test               # 运行测试"
