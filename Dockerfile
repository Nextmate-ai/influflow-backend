# 使用Python 3.11官方镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 安装系统依赖和 uv
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    software-properties-common \
    git \
    && rm -rf /var/lib/apt/lists/* \
    && curl -LsSf https://astral.sh/uv/install.sh | sh

# 将 uv 添加到 PATH
ENV PATH="/root/.local/bin:$PATH"

# 复制项目配置文件（用于依赖解析）
COPY pyproject.toml uv.lock ./

# 使用 uv 安装依赖（基于 uv.lock 中的精确版本），但不安装项目本身
RUN uv sync --frozen --no-dev --no-install-project

# 复制其余项目文件
COPY . .

# 安装项目本身（可选，如果需要可编辑安装）
RUN uv pip install -e . --no-deps

# 暴露Streamlit默认端口
EXPOSE 8501

# 设置Streamlit配置
RUN mkdir -p ~/.streamlit
RUN echo "\
[general]\n\
email = \"\"\n\
" > ~/.streamlit/credentials.toml

RUN echo "\
[server]\n\
headless = true\n\
enableCORS = false\n\
enableXsrfProtection = false\n\
port = 8501\n\
" > ~/.streamlit/config.toml

# 健康检查
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

# 使用 uv 运行应用
CMD ["uv", "run", "python", "start.py"] 