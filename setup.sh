#!/bin/bash
#============================================
# HeiMaClaw 一键配置脚本（非交互式）
#============================================
# 使用方法:
#   1. 修改下方配置参数
#   2. 执行: bash setup.sh
#============================================

#========= LLM 配置 =========
LLM_API_KEY="7dea35ded52043a683b875bae5a31213.uXrxigWPdXxBQHo0"
LLM_MODEL="glm-5"
LLM_BASE_URL="https://open.bigmodel.cn/api/coding/paas/v4"

#========= Vision 配置 =========
VISION_ENABLED="false"
VISION_API_KEY=""
VISION_MODEL="glm-4v"
VISION_BASE_URL="https://open.bigmodel.cn/api/coding/paas/v4"

#========= 飞书配置 =========
FEISHU_APP_ID="cli_a9301fec40395bde"
FEISHU_APP_SECRET="EWPY3k4fjiMpL5iJx6PFFhEzhLsMMkXd"

#============================================
# 以下内容不需要修改
#============================================

set -e

CONFIG_PATH="/opt/heimaclaw/config/config.toml"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== HeiMaClaw 配置脚本 ==="

# 检查是否以 root 运行
if [ "$EUID" -ne 0 ]; then 
    echo "请使用 root 权限运行: sudo bash setup.sh"
    exit 1
fi

# 初始化配置（如果不存在）
if [ ! -f "$CONFIG_PATH" ]; then
    echo "[1/5] 初始化配置文件..."
    mkdir -p "$(dirname $CONFIG_PATH)"
    cat > "$CONFIG_PATH" << 'EOF'
[llm]
provider = "openai"
model = "glm-5"
base_url = "https://open.bigmodel.cn/api/coding/paas/v4"
api_key = ""
max_tokens = 4096
temperature = 0.7

[vision]
enabled = false
model = "glm-4v"
base_url = "https://open.bigmodel.cn/api/coding/paas/v4"
api_key = ""
timeout = 60
max_retries = 3

[channels.feishu]
app_id = ""
app_secret = ""

[sandbox]
enabled = true
memory_mb = 128
cpu_count = 1

[server]
host = "0.0.0.0"
port = 8000
workers = 4

[logging]
level = "INFO"
file = "/opt/heimaclaw/logs/heimaclaw.log"
EOF
    echo "  ✓ 配置文件已创建: $CONFIG_PATH"
else
    echo "[1/5] 配置文件已存在，跳过初始化"
fi

# 配置 LLM
echo "[2/5] 配置 LLM..."
heimaclaw config set llm.api_key "$LLM_API_KEY"
heimaclaw config set llm.model "$LLM_MODEL"
heimaclaw config set llm.base_url "$LLM_BASE_URL"
echo "  ✓ LLM 配置完成"

# 配置 Vision
echo "[3/5] 配置 Vision..."
heimaclaw config set vision.enabled "$VISION_ENABLED"
heimaclaw config set vision.api_key "$VISION_API_KEY"
heimaclaw config set vision.model "$VISION_MODEL"
heimaclaw config set vision.base_url "$VISION_BASE_URL"
echo "  ✓ Vision 配置完成"

# 配置飞书
echo "[4/5] 配置飞书..."
heimaclaw config set channels.feishu.app_id "$FEISHU_APP_ID"
heimaclaw config set channels.feishu.app_secret "$FEISHU_APP_SECRET"
echo "  ✓ 飞书配置完成"

# 显示配置
echo "[5/5] 显示当前配置..."
heimaclaw config show

echo ""
echo "=== 配置完成 ==="
echo "下一步: heimaclaw start --feishu --multi-process"
