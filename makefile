# Influflow - Twitter Thread Generator
# 使用 uv 运行应用的 Makefile

.PHONY: help run-ui run-langgraph test test-quick-validation test-tweet-generate

# 默认目标：显示帮助信息
all: help

# 启动 Streamlit UI 界面
run-ui:
	uv run python start.py

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
	@echo "可用命令:"
	@echo "  run-ui              启动 Streamlit UI 界面"
	@echo "  run-langgraph       启动 LangGraph 开发服务器"
	@echo "  test                运行所有测试"
	@echo "  test-quick-validation  运行推文生成单一测试"
	@echo "  test-tweet-generate 运行推文生成测试"
	@echo "  help                显示此帮助信息"
	@echo ""
	@echo "使用示例:"
	@echo "  make run-ui        # 启动 Web 界面"
	@echo "  make run-langgraph # 启动图形化调试界面"
	@echo "  make test          # 运行所有测试"
	@echo "  make test-quick-validation # 运行快速验证测试"
	@echo "  make test-tweet-generate   # 运行推文生成测试"
