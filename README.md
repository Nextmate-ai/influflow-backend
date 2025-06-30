# Influflow - Twitter Thread Generator

Influflow 是一个基于 LangGraph 的 Twitter Thread 生成器，能够自动生成高质量、结构化的推特线程。它使用智能工作流来分析主题，创建大纲，并生成符合推特字符限制的内容。

### 🚀 功能特色

- **智能生成**: 基于输入主题自动生成结构化的 Twitter Thread
- **多语言支持**: 支持中文和英文内容生成
- **字符统计**: 自动统计每条推文的字符数，确保符合 Twitter 限制
- **模型选择**: 支持多种 OpenAI 模型（GPT-4o、GPT-4o-mini 等）
- **简洁UI**: 基于 Streamlit 的直观用户界面
- **历史记录**: 保存生成历史，方便查看和管理

### 🏃 快速开始

1. **克隆仓库:**
   ```bash
   git clone <your-repo-url>
   cd influflow-backend
   ```

2. **设置环境:**
   
   复制示例环境文件并添加你的 API 密钥：
   ```bash
   cp .env.example .env
   ```
   
   在 `.env` 文件中设置：
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   ```

3. **安装依赖:**

   **使用 `uv` (推荐方式):**
   ```bash
   # 安装 uv（如果尚未安装）
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # 创建虚拟环境并按照 uv.lock 安装精确版本的依赖
   uv sync
   ```

   **使用 `pip` (传统方式):**
   ```bash
   # 创建并激活虚拟环境
   python -m venv .venv
   source .venv/bin/activate  # Windows 使用 `.venv\Scripts\activate`

   # 安装依赖
   pip install -e ".[dev]"
   ```

4. **启动应用:**
   
   **使用 Makefile（最便捷）:**
   ```bash
   # 启动 Streamlit UI 界面
   make run-ui
   
   # 启动 LangGraph 开发服务器（可选）
   make run-langgraph
   
   # 查看所有可用命令
   make help
   ```
   
   **使用 `uv` (推荐):**
   ```bash
   # 使用 uv 运行，自动使用虚拟环境和锁定版本
   uv run python start.py
   ```
   
   **使用激活的虚拟环境:**
   ```bash
   # 手动激活虚拟环境后运行
   source .venv/bin/activate  # Windows 使用 `.venv\Scripts\activate`
   python start.py
   ```
   
   这将在浏览器中打开用户界面。

5. **运行 LangGraph 平台（可选）:**

   你也可以使用 LangGraph 平台进行开发和测试：

   ```bash
   # 使用 uv 运行 LangGraph 开发服务器
   uv run uvx --refresh --from "langgraph-cli[inmem]" --with-editable . --python 3.11 langgraph dev --allow-blocking
   ```
   
   这将启动 LangGraph 开发服务器，提供图形化界面来调试和测试工作流。

### 💡 依赖管理说明

项目使用 `uv.lock` 文件确保所有环境使用完全相同的依赖版本：

- **开发时**: 使用 `uv run python start.py` 确保使用锁定版本
- **添加依赖**: `uv add package-name` 
- **更新依赖**: `uv sync`
- **部署时**: Docker 和 Railway 会自动使用 `uv.lock` 中的精确版本

这解决了"在我电脑上能运行"的版本不一致问题。

---

### 🚢 部署 Deployment

### Railway 云部署
   ```bash
   # 推送到 prod 分支会自动触发部署, Push 或者 PR 合入prod分支
   git push prod
   ```

Railway 会自动检测并使用项目中的 `Dockerfile`，确保使用 `uv.lock` 中的精确依赖版本。


> ⚠️ 请勿将包含敏感信息的 `.env` 文件提交到公共仓库，务必通过平台 Secrets 或环境变量注入。

### 📝 使用方法

1. **输入主题**: 在输入框中描述你想要创建 Twitter Thread 的主题
2. **选择配置**: 在侧边栏选择模型和语言
3. **生成内容**: 点击"生成Thread"按钮，系统将：
   - 分析主题并创建大纲结构
   - 生成符合字符限制的推文内容
   - 提供可复制的格式化输出
4. **查看结果**: 在"生成结果"区域查看大纲和推文内容
5. **下载内容**: 可以下载大纲和推文内容到本地文件

### 🛠️ 技术架构

- **核心引擎**: LangGraph - 用于构建智能工作流
- **用户界面**: Streamlit - 提供简洁的Web界面
- **AI模型**: OpenAI GPT模型 - 负责内容生成
- **状态管理**: 基于Pydantic的类型安全状态管理

### ⚙️ 高级配置

#### 自定义模型配置

你可以通过修改配置来使用不同的模型：

```python
# 在 configuration.py 中自定义模型设置
config = {
    "writer_provider": "openai",
    "writer_model": "gpt-4o",  # 或其他支持的模型
    "writer_model_kwargs": {}  # 模型参数
}
```

### 🗂️ 项目结构

```
influflow-backend/
├── 📄 README.md           # 项目说明文档
├── 🚀 start.py            # 应用启动脚本，配置Streamlit服务器
├── 📦 pyproject.toml       # Python项目配置文件，定义依赖和构建设置
├── 🔒 uv.lock             # 依赖版本锁定文件，确保环境一致性
├── ⚙️ makefile            # 便捷命令脚本，提供快速启动和管理命令
├── 🐳 Dockerfile          # Docker容器构建文件，用于云端部署
├── 🚂 railway.json        # Railway平台部署配置文件
├── 📋 langgraph.json      # LangGraph开发服务器配置文件
├── 🔧 deploy_check.py     # 部署环境检查脚本，验证配置和依赖
├── 📜 LICENSE             # 项目许可证文件 (MIT)
└── 📁 src/
    └── influflow/          # 主要代码目录
        ├── __init__.py     # Python包初始化文件
        ├── configuration.py # 工作流配置管理
        ├── graph.py        # LangGraph工作流定义
        ├── prompt.py       # AI提示词模板
        ├── state.py        # 状态管理和数据模型
        ├── ui.py           # Streamlit用户界面
        └── utils.py        # 工具函数和辅助方法
```

#### 📄 根目录文件说明

| 文件 | 作用说明 |
|------|----------|
| `start.py` | **应用启动脚本** - 配置Streamlit服务器，设置端口、环境变量，验证API密钥，是应用的入口点 |
| `pyproject.toml` | **项目配置文件** - 定义项目元数据、依赖包、构建配置、代码质量工具(ruff)设置 |
| `uv.lock` | **依赖锁定文件** - 记录所有依赖包的精确版本，确保开发、测试、部署环境完全一致 |
| `makefile` | **便捷命令脚本** - 提供快速启动命令(run-ui, run-langgraph)和帮助信息，简化开发流程 |
| `Dockerfile` | **容器构建文件** - 定义Docker镜像构建步骤，支持云平台部署，基于uv进行依赖管理 |
| `railway.json` | **Railway部署配置** - 指定Railway平台的构建和部署设置，包括构建命令和启动命令 |
| `langgraph.json` | **LangGraph配置** - 配置LangGraph开发服务器，用于图形化调试和测试工作流 |
| `deploy_check.py` | **部署检查脚本** - 验证部署环境的Python版本、依赖安装、API连接等，排查部署问题 |
| `LICENSE` | **开源许可证** - MIT许可证文件，定义项目的使用和分发条款 |

#### 🧩 核心模块说明

| 模块 | 功能描述 |
|------|----------|
| `graph.py` | **工作流引擎** - 定义LangGraph工作流，包含Twitter Thread生成的核心逻辑 |
| `state.py` | **状态管理** - 使用Pydantic定义数据模型，管理工作流状态和结构化输出 |
| `ui.py` | **用户界面** - Streamlit Web界面，提供主题输入、配置选择、结果展示功能 |
| `prompt.py` | **提示词管理** - 存储和管理AI模型的提示词模板，支持多语言生成 |
| `configuration.py` | **配置管理** - 定义工作流配置选项，支持模型选择和参数调整 |
| `utils.py` | **工具函数** - 提供通用的辅助函数和配置读取方法 |

---