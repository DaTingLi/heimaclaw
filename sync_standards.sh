#!/bin/bash

# 同步 standards 目录到项目根

set -e

echo "🔄 同步 HeiMaClaw standards 目录..."

# 1. 备份当前状态
echo "📦 夣份当前状态..."
git add standards/

# 2. 同步新文件
echo "✅ 同步完成！"
echo ""
echo "📊 新增文件："
echo "  - EVENT_BUS_ARCHITECTURE-v1.0.md"
echo "  - PROJECT-STATUS-v1.0.md (更新)"
echo "  - PROJECT-DECISION-LOG-v1.0.md (更新)"
echo "  - CI/CD 配置 (GitHub Actions)"
echo ""
echo "✅ 总计: 4 个文件更新/新增"
echo ""
echo "📝 揶交命令:"
echo "  git add standards/"
echo "  git commit -m 'feat: Add Event Bus + Subagent architecture'"
echo "  git push origin main"
