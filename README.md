# Open Deep Research

Open Deep Research is an experimental, fully open-source research assistant that automates deep research and produces comprehensive reports on any topic. It uses a [LangGraph](https://langchain-ai.github.io/langgraph/) workflow to structure the research process. You can customize the entire research and writing process with specific models, prompts, report structure, and search tools.

### 🚀 Workflow

![open-deep-research-overview](https://github.com/user-attachments/assets/a171660d-b735-4587-ab2f-cd771f773756)

### 🏃 Quickstart

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/langchain-ai/open_deep_research.git
    cd open_deep_research
    ```

2.  **Set up your environment:**

    Copy the example environment file and edit it to add your API keys for language models and search tools.
    ```bash
    cp .env.example .env
    ```

3.  **Install dependencies and run the application:**

    The application includes a Streamlit-based user interface.

    *   **Using `uv` (recommended for Mac/Linux):**
        ```bash
        # Install uv
        curl -LsSf https://astral.sh/uv/install.sh | sh

        # Create a virtual environment and install dependencies
        uv venv
        source .venv/bin/activate
        uv pip install -e ".[dev]"
        ```

    *   **Using `pip` (for Windows/Linux):**
        ```bash
        # Create and activate a virtual environment
        python -m venv .venv
        source .venv/bin/activate  # On Windows use `.venv\Scripts\activate`

        # Install dependencies
        pip install -e ".[dev]"
        ```

4.  **Launch the UI:**
    ```bash
    python start.py
    ```
    This will open the user interface in your browser.

5.  **运行 LangGraph 平台（可选）:**

    除了 Streamlit UI，你也可以使用 LangGraph 平台进行开发和测试：

    ```bash
    # 安装 uv 包管理器（如果尚未安装）
    curl -LsSf https://astral.sh/uv/install.sh | sh

    # 安装依赖并启动 LangGraph 开发服务器
    BG_JOB_ISOLATED_LOOPS=true uvx --refresh --from "langgraph-cli[inmem]" --with-editable . --python 3.11 langgraph dev --allow-blocking
    ```
    
    这将启动 LangGraph 开发服务器，提供图形化界面来调试和测试工作流。

---

### 🚢 部署 Deployment

#### 1. Docker 本地/服务器部署

仓库已提供 `Dockerfile`，可一键构建镜像并运行：
```bash
# 构建镜像（如需自定义TAG可自行修改）
docker build -t open-deep-research:latest .

# 运行容器，映射默认的 8501 端口
# 请用 -e 传递模型 / 搜索 API KEY，或挂载自定义 .env 文件

docker run -it --rm -p 8501:8501 \
  -e OPENAI_API_KEY=your_key \
  -e TAVILY_API_KEY=your_key \
  open-deep-research:latest
```
启动后访问 `http://localhost:8501` 即可。

#### 2. Railway 云部署

已提供 `railway.json` 配置与辅助脚本 `deploy.sh`：
```bash
# 安装依赖（需先安装 Node & npm）
npm install -g @railway/cli

# 一键创建并部署（会提示输入 API KEY）
./deploy.sh
```
脚本会自动：
1. 检查/安装 Railway CLI 并登录。
2. 创建名为 `open-deep-research` 的项目。
3. 根据提示写入环境变量。
4. 使用 `Dockerfile` 构建并部署。

部署完成后，可在 Railway Dashboard 查看 URL 与日志。

#### 3. 其他平台
- **Streamlit Community Cloud / Hugging Face Spaces**：入口文件均为 `start.py`；将 `.env` 中的变量填入各平台的 Secrets 即可。
- **Vercel / Netlify**：建议先用 Docker 容器或 Cloud Run 部署后再做反向代理。

> ⚠️ 请勿将包含敏感信息的 `.env` 文件提交到公共仓库，务必通过平台 Secrets 或命令行 `-e` 参数注入。

### 📝 How to Use

1.  **Enter a topic** for your research in the input box.
2.  The system will generate a **research plan**. You can review it.
3.  If you are satisfied with the plan, click **"Accept"** to proceed. If you want to modify it, provide your feedback in the text box and click **"Regenerate"**.
4.  Once the plan is accepted, the workflow will execute the research and generate a **comprehensive report** in Markdown format.

### 🛠️ Search Tools

You can configure the workflow to use various search tools. Set your preferences and API keys in the `.env` file.

*   [Tavily API](https://tavily.com/)
*   [Perplexity API](https://www.perplexity.ai/)
*   [Exa API](https://exa.ai/)
*   [ArXiv](https://arxiv.org/)
*   [PubMed](https://pubmed.ncbi.nlm.nih.gov/)
*   [Linkup API](https://www.linkup.so/)
*   [DuckDuckGo API](https://duckduckgo.com/)
*   [Google Search API](https://developers.google.com/custom-search/v1/introduction)
*   [Microsoft Azure AI Search](https://azure.microsoft.com/en-us/products/ai-services/ai-search)

### ⚙️ Advanced Configuration

#### Customizing the Workflow

You can customize the research workflow through several parameters:

- `report_structure`: Define a custom structure for your report.
- `number_of_queries`: Number of search queries to generate per section (default: 2).
- `max_search_depth`: Maximum number of reflection and search iterations (default: 2).
- `planner_provider` / `planner_model`: The model used for planning the report.
- `writer_provider` / `writer_model`: The model used for writing the report sections.
- `search_api`: The search API to use.

#### Search API Configuration

Some search APIs support additional configuration parameters.

- **Exa**: `max_characters`, `num_results`, `include_domains`, `exclude_domains`, `subpages`
- **ArXiv**: `load_max_docs`, `get_full_documents`, `load_all_available_meta`
- **PubMed**: `top_k_results`, `email`, `api_key`, `doc_content_chars_max`
- **Linkup**: `depth`

Example with Exa configuration:
```python
thread = {"configurable": {"thread_id": str(uuid.uuid4()),
                           "search_api": "exa",
                           "search_api_config": {
                               "num_results": 5,
                               "include_domains": ["nature.com", "sciencedirect.com"]
                           },
                           # Other configuration...
                           }}
```

### 🤖 Model Considerations

1.  **Model Support**: You can use models supported by [the `init_chat_model()` API](https://python.langchain.com/docs/how_to/chat_models_universal_init/).
2.  **Structured Outputs**: The workflow's planner and writer models must support structured outputs/function calling. Check your model provider's documentation. Models from OpenAI, Anthropic, and Google generally work well.
3.  **Local Models**: For guidance on using local models with Ollama, see [this issue](https://github.com/langchain-ai/open_deep_research/issues/65#issuecomment-2743586318).

### 🧪 Evaluation

The project includes a `pytest`-based evaluation system to assess report quality.

- **Run evaluation:**
  ```bash
  # Test with specific models
  python tests/run_test.py --planner-model "openai:gpt-4o" --writer-model "openai:gpt-4o" --eval-model "openai:gpt-4o"
  ```
- **Key Files:**
  - `tests/run_test.py`: Main test runner.
  - `tests/test_report_quality.py`: Core test implementation.
  - `tests/conftest.py`: Pytest configuration.

### 🤝 Contributing

Contributions are welcome! Please feel free to open an issue or submit a pull request.

### 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
- Gate-keeping before production deployments

**Use LangSmith System for:**
- Comprehensive model evaluation across datasets
- Research and analysis of system performance
- Detailed performance profiling and benchmarking
- Comparative studies between different configurations
- Production monitoring and quality assurance

Both evaluation systems complement each other and provide comprehensive coverage for different use cases and development stages.

## UX

### Local deployment

Follow the [quickstart](#-quickstart) to start LangGraph server locally.

### Hosted deployment
 
You can easily deploy to [LangGraph Platform](https://langchain-ai.github.io/langgraph/concepts/#deployment-options). 
