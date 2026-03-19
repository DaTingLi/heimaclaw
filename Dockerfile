FROM python:3.10-slim

LABEL maintainer="heimaclaw@example.com"
LABEL description="HeiMaClaw - 生产级企业 AI Agent 平台"

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制项目
COPY . /app/

# 安装
RUN pip install --no-cache-dir -e .

# 创建必要目录
RUN mkdir -p /opt/heimaclaw/{config,logs,data,sandboxes}

# 暴露端口
EXPOSE 8000

# 启动
CMD ["heimaclaw", "start", "--host", "0.0.0.0"]
