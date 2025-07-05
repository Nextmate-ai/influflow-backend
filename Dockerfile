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
    supervisor \
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

# 暴露UI和API端口
EXPOSE 8501 8000

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

# 创建supervisor配置文件来同时管理UI和API服务
RUN echo "\
[supervisord]\n\
nodaemon=true\n\
user=root\n\
\n\
[program:api]\n\
command=uv run uvicorn influflow.api.main:app --host 0.0.0.0 --port 8000\n\
directory=/app\n\
autostart=true\n\
autorestart=true\n\
stderr_logfile=/var/log/api.err.log\n\
stdout_logfile=/var/log/api.out.log\n\
\n\
[program:ui]\n\
command=uv run streamlit run src/influflow/ui.py --server.port=8501 --server.address=0.0.0.0 --server.headless=true --server.enableCORS=false --server.enableXsrfProtection=false --browser.gatherUsageStats=false\n\
directory=/app\n\
autostart=true\n\
autorestart=true\n\
stderr_logfile=/var/log/ui.err.log\n\
stdout_logfile=/var/log/ui.out.log\n\
" > /etc/supervisor/conf.d/supervisord.conf

# 健康检查 - 检查两个服务是否都在运行
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl --fail http://localhost:8501/_stcore/health && \
      curl --fail http://localhost:8000/health || exit 1

# 使用supervisor同时启动UI和API服务
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"] 