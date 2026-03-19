#!/bin/bash
set -e

# ============================================
# HeiMaClaw Docker 一键部署脚本 v1.0
# ============================================
# 要求: Docker 20.10+
# ============================================

echo "=========================================="
echo "  HeiMaClaw Docker 一键部署"
echo "=========================================="

# 构建 Docker 镜像
echo "构建 Docker 镜像..."
docker build -t heimaclaw:latest . -f Dockerfile

# 运行容器
echo "启动容器..."
docker run -d \
    --name heimaclaw \
    -p 8000:8000 \
    -v /opt/heimaclaw/data:/opt/heimaclaw/data \
    --restart unless-stopped \
    heimaclaw:latest

echo ""
echo "✅ 部署完成!"
echo "访问地址: http://localhost:8000"
echo ""
echo "常用命令:"
echo "  docker logs -f heimaclaw  # 查看日志"
echo "  docker exec -it heimaclaw heimaclaw doctor  # 诊断"
echo "  docker stop heimaclaw      # 停止"
