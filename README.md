# InfluFlow - AI-Powered Twitter Thread Generator

InfluFlow 是一个现代化的 AI 工具后端，专注于 Twitter Thread 的智能生成与编辑。基于 LangGraph 工作流引擎，提供了完整的 HTTP API 接口和用户友好的 Web 界面。

### 🚀 核心功能

- **🤖 智能生成**: 基于主题自动生成结构化的 Twitter Thread
- **✏️ 精准编辑**: 支持单条推文修改和整体大纲重构  
- **🌍 多语言支持**: 支持中文和英文内容生成
- **📊 字符统计**: 自动统计推文字符数，确保符合 Twitter 限制
- **🎛️ 模型选择**: 支持多种 OpenAI 模型（GPT-4o、GPT-4o-mini 等）
- **🔌 HTTP API**: 完整的 RESTful API，支持程序化调用
- **🎨 双界面模式**: Web UI（调试）+ API（集成）
- **📱 响应式设计**: 现代化的用户界面设计
- **📚 自动文档**: 自动生成的 API 文档（Swagger UI）

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

   **🔌 启动 API 服务器（推荐）:**
   ```bash
   # 启动 FastAPI 服务器
   python start_api.py
   # 或者
   python start.py api
   ```
   
   API 将在 http://localhost:8000 启动
   - API 文档: http://localhost:8000/docs
   - ReDoc 文档: http://localhost:8000/redoc
   
   **🎨 启动 Web UI（调试用）:**
   ```bash
   # 启动重构后的 UI
   python start_ui.py
   # 或者
   python start.py ui
   ```
   
   UI 将在 http://localhost:8501 启动
   
   **☁️ 云平台部署模式:**
   ```bash
   # 兼容原有部署方式
   python start.py cloud
   ```
   
   **📊 使用 Makefile（便捷命令）:**
   ```bash
   make run-ui          # 启动 UI
   make run-langgraph   # 启动 LangGraph 开发服务器
   make help           # 查看所有命令
   ```

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

### 🚢 部署 Deployment

### Railway 云部署
   ```bash
   # 推送到 prod 分支会自动触发部署, Push 或者 PR 合入prod分支
   git push prod
   ```

Railway 会自动检测并使用项目中的 `Dockerfile`，确保使用 `uv.lock` 中的精确依赖版本。


> ⚠️ 请勿将包含敏感信息的 `.env` 文件提交到公共仓库，务必通过平台 Secrets 或环境变量注入。

### 📝 使用方法

#### 🔌 API 使用方式（推荐）


Swagger UI: http://localhost:8000/docs

#### 🎨 Web UI 使用方式

1. **输入主题**: 在输入框中描述你想要创建 Twitter Thread 的主题
2. **选择配置**: 在侧边栏选择模型和语言
3. **生成内容**: 点击"生成Thread"按钮，系统将自动生成结构化内容
4. **编辑优化**: 可以修改单条推文或重构整个大纲
5. **查看结果**: 实时预览推文内容和字符统计
6. **导出内容**: 下载大纲和推文内容到本地文件

### 🏗️ 技术架构

采用现代化的分层架构设计：

- **API 层**: FastAPI + Pydantic - 提供 RESTful HTTP 接口
- **服务层**: 业务逻辑抽象 - API 和 UI 共享核心功能  
- **AI 层**: LangGraph 工作流 - 智能内容生成引擎
- **数据层**: Pydantic 模型 - 类型安全的状态管理

#### 核心技术栈
- **🤖 AI 引擎**: LangGraph + OpenAI GPT 模型
- **🔌 API 框架**: FastAPI + Uvicorn
- **🎨 UI 框架**: Streamlit
- **📋 数据模型**: Pydantic
- **⚙️ 配置管理**: 环境变量 + YAML
- **📦 依赖管理**: UV + lockfile

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
├── 📄 README.md            # 项目说明文档
├── 🚀 start.py             # 统一启动脚本（支持api/ui/cloud模式）
├── 🔌 start_api.py         # FastAPI服务器启动脚本
├── 🎨 start_ui.py          # Streamlit UI启动脚本
├── 📦 pyproject.toml       # Python项目配置文件
├── 🔒 uv.lock             # 依赖版本锁定文件
├── ⚙️ makefile            # 便捷命令脚本
├── 🐳 Dockerfile          # Docker容器构建文件
├── 🚂 railway.json        # Railway平台部署配置
├── 📋 langgraph.json      # LangGraph开发服务器配置
├── 📜 LICENSE             # MIT许可证文件
├── 📁 test/               # 测试文件目录
└── 📁 src/
    └── influflow/          # 主代码目录
        ├── __init__.py     # 主模块入口，导出核心组件
        ├── ui.py           # 原版Streamlit界面
        ├── 🔌 api/         # FastAPI应用层
        │   ├── __init__.py
        │   ├── main.py     # FastAPI主应用
        │   └── models.py   # API请求/响应模型
        ├── ⚙️ services/    # 业务逻辑服务层
        │   ├── __init__.py
        │   └── twitter_service.py # Twitter AI服务
        └── 🤖 ai/          # AI模块（核心智能功能）
            ├── __init__.py         # AI模块入口
            ├── state.py           # AI状态和数据模型
            ├── configuration.py   # AI配置管理
            ├── prompt.py          # AI提示词模板
            ├── utils.py           # AI工具函数
            └── graph/             # LangGraph工作流
                ├── __init__.py
                ├── generate_tweet.py          # 生成推文工作流
                ├── modify_single_tweet.py     # 修改单条推文工作流
                └── modify_outline_structure.py # 修改大纲结构工作流
```

#### 🏗️ 分层架构说明

| 层级 | 目录 | 职责描述 |
|------|------|----------|
| **🔌 API层** | `api/` | FastAPI路由，HTTP请求/响应处理，参数验证，API文档 |
| **⚙️ 服务层** | `services/` | 业务逻辑封装，API和UI共享，异步处理，错误管理 |
| **🤖 AI层** | `ai/` | LangGraph工作流，AI模型调用，状态管理，提示词工程 |
| **🎨 展示层** | `ui*.py` | Streamlit界面，用户交互，结果展示，调试功能 |

#### 📁 核心目录详解

**🔌 API层 (`api/`)**
- `main.py` - FastAPI应用入口，路由定义，中间件配置
- `models.py` - Pydantic模型，请求/响应结构，数据验证

**⚙️ 服务层 (`services/`)**  
- `twitter_service.py` - Twitter AI核心服务，同步/异步接口，业务逻辑

**🤖 AI层 (`ai/`)**
- `state.py` - Pydantic数据模型，状态定义，类型安全
- `configuration.py` - AI配置管理，模型参数，工作流设置
- `prompt.py` - 提示词模板，多语言支持，模板管理
- `utils.py` - AI工具函数，辅助方法，配置读取
- `graph/` - LangGraph工作流目录
  - `generate_tweet.py` - 生成推文的核心工作流
  - `modify_single_tweet.py` - 单条推文修改工作流
  - `modify_outline_structure.py` - 大纲结构修改工作流

#### 🚀 启动脚本说明

| 脚本 | 用途 | 端口 |
|------|------|------|
| `start_api.py` | 启动FastAPI服务器 | 8000 |
| `start_ui.py` | 启动重构版UI | 8501 |
| `start.py api` | 统一启动API模式 | 8000 |
| `start.py ui` | 统一启动UI模式 | 8501 |
| `start.py cloud` | 云平台部署模式 | 环境变量 |

#### 🔄 数据流向

```
UI/API请求 → 服务层(twitter_service) → AI层(LangGraph) → OpenAI API → 结果返回
     ↓              ↓                    ↓                    ↓
  用户界面      业务逻辑封装         AI工作流处理         模型推理
```

### 🔌 API 接口一览

| 端点 | 方法 | 功能 | 状态 |
|------|------|------|------|
| `/health` | GET | 健康检查 | ✅ |
| `/api/twitter/generate` | POST | 生成Twitter Thread | ✅ |
| `/api/twitter/modify-tweet` | POST | 修改单条推文 | ✅ |
| `/api/twitter/modify-outline` | POST | 修改大纲结构 | ✅ |
| `/docs` | GET | Swagger API文档 | ✅ |
| `/redoc` | GET | ReDoc API文档 | ✅ |

### 🧪 测试与开发

**运行项目测试:**
```bash
# 运行所有测试
pytest test/

# 运行特定测试
python -m pytest test/test_tweet_generate.py -v
```

### 📈 扩展指南

基于当前的分层架构，可以轻松添加新功能：

1. **新增AI模块**: 在 `ai/` 下创建新的子模块
2. **新增API接口**: 在 `api/` 下添加新的路由
3. **新增服务**: 在 `services/` 下创建新的服务类
4. **新增UI功能**: 扩展现有UI或创建新的UI组件

### 🤝 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request



---

**🌟 Star this repo if you find it helpful!**

© 2024 InfluFlow. Licensed under [MIT License](LICENSE).