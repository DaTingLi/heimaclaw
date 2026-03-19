#!/bin/bash

# HeiMaClaw Event Bus + Subagent 部署脚本

set -e

echo "🚀 开始部署 HeiMaClaw Event Bus + Subagent 架构..."

# 1. 检查核心文件
echo "✅ 检查核心文件..."
FILES=(
    "src/heimaclaw/core/__init__.py"
    "src/heimaclaw/core/event_bus.py"
    "src/heimaclaw/core/subagent_registry.py"
    "src/heimaclaw/core/subagent_spawn.py"
    "src/heimaclaw/core/integration_example.py"
)

for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "  ✓ $file"
    else
        echo "  ✗ $file 缺失！"
        exit 1
    fi
done

# 2. 创建测试文件
echo "✅ 检查测试文件..."
TEST_FILES=(
    "tests/core/__init__.py"
    "tests/core/test_event_bus.py"
    "tests/core/test_subagent_registry.py"
)

for file in "${TEST_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "  ✓ $file"
    else
        echo "  ✗ $file 缺失！"
        exit 1
    fi
done

# 3. 检查文档
if [ -f "docs/EVENT_BUS_SUBAGENT.md" ]; then
    echo "  ✓ 文档已创建"
else
    echo "  ✗ 文档缺失！"
    exit 1
fi

# 4. 运行单元测试
echo ""
echo "🧪 运行单元测试..."
python -m pytest tests/core/ -v

# 5. 检查依赖
echo ""
echo "📦 检查依赖..."
pip install aiofiles pydantic pytest pytest-asyncio

echo ""
echo "✅ 部署完成！"
echo ""
echo "📖 快速开始："
echo "  1. 查看文档: cat docs/EVENT_BUS_SUBAGENT.md"
echo "  2. 运行示例: python -m heimaclaw.core.integration_example"
echo "  3. 查看测试: pytest tests/core/ -v"
echo ""
