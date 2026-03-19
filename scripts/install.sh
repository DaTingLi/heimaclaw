#!/bin/bash
set -e

# ============================================
# HeiMaClaw 一键安装脚本 v3.0
# ============================================
# 支持: Ubuntu 18.04+, Debian 10+, CentOS 7+, 国产OS
# 特性: 自动安装依赖、使用国内镜像、对小白友好
# ============================================

set -e

echo "=========================================="
echo "  HeiMaClaw 一键安装脚本 v3.0"
echo "=========================================="
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${CYAN}[STEP]${NC} $1"; }
log_ok() { echo -e "${GREEN}[OK]${NC} $1"; }

# 检测是否为中国用户（网络慢）
detect_china_user() {
    # 检测是否使用国内网络
    if curl -s --max-time 2 https://pypi.tuna.tsinghua.edu.cn/simple > /dev/null 2>&1; then
        echo "tsinghua"
    elif curl -s --max-time 2 https://mirrors.aliyun.com/pypi/simple > /dev/null 2>&1; then
        echo "aliyun"
    else
        echo "pypi"
    fi
}

PYPI_MIRROR=""

# ============================================
# 环境检测
# ============================================
check_environment() {
    echo "=========================================="
    echo "  第一步：环境检测"
    echo "=========================================="
    echo ""
    
    # 检测 Python
    log_step "检测 Python..."
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
        PYTHON_FULL=$(python3 --version)
        log_ok "检测到 Python $PYTHON_FULL"
        
        # 检查版本
        PYTHON_MAJOR=$(python3 -c 'import sys; print(sys.version_info[0])')
        PYTHON_MINOR=$(python3 -c 'import sys; print(sys.version_info[1])')
        
        if [[ $PYTHON_MAJOR -gt 3 ]] || [[ $PYTHON_MAJOR -eq 3 && $PYTHON_MINOR -ge 10 ]]; then
            log_ok "Python 版本满足要求 (>= 3.10)"
            return 0
        else
            log_warn "Python 版本过低: $PYTHON_VERSION (需要 >= 3.10)"
            return 1
        fi
    else
        log_error "未检测到 Python3"
        return 1
    fi
    
    # 检测 netcat
    echo ""
    log_step "检测 netcat..."
    if command -v nc &> /dev/null; then
        log_ok "netcat 已安装"
    else
        log_warn "netcat 未安装，将自动安装..."
        apt-get install -y netcat || yum install -y nc || true
    fi
    
    # 检测端口
    echo ""
    log_step "检测端口 8000..."
    if command -v nc &> /dev/null; then
        if nc -z localhost 8000 2>/dev/null; then
            log_warn "端口 8000 已被占用"
            log_info "HeiMaClaw 可使用其他端口: heimaclaw start --port 8080"
        else
            log_ok "端口 8000 可用"
        fi
    else
        log_info "无法检测端口（netcat 未安装）"
    fi
    
    echo ""
}

# ============================================
# 安装依赖
# ============================================
install_dependencies() {
    echo ""
    echo "=========================================="
    echo "  第二步：安装系统依赖"
    echo "=========================================="
    echo ""
    
    log_step "更新软件包列表..."
    if command -v apt-get &> /dev/null; then
        apt-get update -qq
    elif command -v yum &> /dev/null; then
        yum check-update -q || true
    fi
    log_ok "软件包列表已更新"
    
    echo ""
    log_step "安装 netcat（端口检测用）..."
    if command -v apt-get &> /dev/null; then
        apt-get install -y -qq netcat-openbsd 2>/dev/null || apt-get install -y -qq netcat 2>/dev/null || true
    elif command -v yum &> /dev/null; then
        yum install -y -q nc 2>/dev/null || true
    fi
    log_ok "netcat 安装完成"
}

# ============================================
# 安装/升级 Python
# ============================================
install_python() {
    echo ""
    echo "=========================================="
    echo "  第三步：检查 Python"
    echo "=========================================="
    echo ""
    
    # 检查版本
    PYTHON_MAJOR=$(python3 -c 'import sys; print(sys.version_info[0])')
    PYTHON_MINOR=$(python3 -c 'import sys; print(sys.version_info[1])')
    
    if [[ $PYTHON_MAJOR -gt 3 ]] || [[ $PYTHON_MAJOR -eq 3 && $PYTHON_MINOR -ge 10 ]]; then
        log_ok "Python 版本已满足要求 (3.${PYTHON_MINOR})"
        return 0
    fi
    
    log_warn "需要安装 Python 3.10+"
    
    echo ""
    log_step "安装 Python 3.10..."
    
    if command -v apt-get &> /dev/null; then
        # Debian/Ubuntu
        apt-get install -y software-properties-common
        add-apt-repository -y ppa:deadsnakes/ppa 2>/dev/null || true
        apt-get update -qq
        apt-get install -y -qq python3.10 python3.10-venv python3.10-dev python3-pip
        update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1 2>/dev/null || true
        update-alternatives --install /usr/bin/pip3 pip3 /usr/bin/pip3.10 1 2>/dev/null || true
        
    elif command -v yum &> /dev/null; then
        # CentOS/RHEL - 使用 IUS 或源码
        yum install -y -q epel-release
        
        # 尝试使用 pyenv 或直接安装
        if command -v pyenv &> /dev/null; then
            pyenv install 3.10.0
            pyenv global 3.10.0
        else
            # 源码编译安装（快速版）
            log_info "正在安装 Python 3.10（自动编译）..."
            yum groupinstall -y -q "Development Tools"
            yum install -y -q openssl-devel bzip2-devel libffi-devel zlib-devel
            
            cd /tmp
            curl -sL https://www.python.org/ftp/python/3.10.0/Python-3.10.0.tgz -o Python-3.10.0.tgz
            tar xzf Python-3.10.0.tgz
            cd Python-3.10.0
            ./configure --enable-optimizations --prefix=/usr/local > /dev/null 2>&1
            make -j$(nproc) > /dev/null 2>&1
            make altinstall > /dev/null 2>&1
            cd /
            rm -rf /tmp/Python-3.10.0*
            
            # 创建符号链接
            ln -sf /usr/local/bin/python3.10 /usr/bin/python3.10
            ln -sf /usr/local/bin/pip3.10 /usr/bin/pip3.10
            ln -sf /usr/bin/python3.10 /usr/bin/python3
            ln -sf /usr/bin/pip3.10 /usr/bin/pip3
        fi
    fi
    
    log_ok "Python 3.10 安装完成"
}

# ============================================
# 安装 HeiMaClaw
# ============================================
install_heimaclaw() {
    echo ""
    echo "=========================================="
    echo "  第四步：安装 HeiMaClaw"
    echo "=========================================="
    echo ""
    
    # 检测镜像
    log_step "检测最佳安装源..."
    PYPI_MIRROR=$(detect_china_user)
    
    if [[ "$PYPI_MIRROR" == "tsinghua" ]]; then
        log_ok "使用清华 PyPI 镜像（国内加速）"
        PIP_EXTRA_INDEX=" -i https://pypi.tuna.tsinghua.edu.cn/simple "
    elif [[ "$PYPI_MIRROR" == "aliyun" ]]; then
        log_ok "使用阿里 PyPI 镜像（国内加速）"
        PIP_EXTRA_INDEX=" -i https://mirrors.aliyun.com/pypi/simple "
    else
        log_info "使用默认 PyPI 源"
        PIP_EXTRA_INDEX=""
    fi
    
    # 检查是否有 wheel 文件
    if [ -f "./dist/heimaclaw-0.1.0-py3-none-any.whl" ]; then
        echo ""
        log_step "使用本地 wheel 安装..."
        pip3 install $PIP_EXTRA_INDEX ./dist/heimaclaw-0.1.0-py3-none-any.whl
    else
        echo ""
        log_step "使用 PyPI 安装..."
        pip3 install $PIP_EXTRA_INDEX heimaclaw
    fi
    
    log_ok "HeiMaClaw 安装完成"
}

# ============================================
# 初始化
# ============================================
init_heimaclaw() {
    echo ""
    echo "=========================================="
    echo "  第五步：初始化项目"
    echo "=========================================="
    echo ""
    
    log_step "创建目录结构..."
    mkdir -p /opt/heimaclaw/{config,logs,data,sandboxes}
    mkdir -p /opt/heimaclaw/data/{agents,sessions}
    mkdir -p /root/.heimaclaw/{agents,sessions}
    log_ok "目录结构已创建"
    
    echo ""
    log_step "初始化配置..."
    if [ ! -f /opt/heimaclaw/config/config.toml ]; then
        cat > /opt/heimaclaw/config/config.toml << 'EOF'
[heimaclaw]
name = "HeiMaClaw"
version = "0.1.0"
environment = "development"

[server]
host = "0.0.0.0"
port = 8000
workers = 1

[sandbox]
enabled = true
backend = "firecracker"
warm_pool_size = 5
max_instances = 100
memory_mb = 128
cpu_count = 1

[channels.feishu]
enabled = false
app_id = ""
app_secret = ""

[channels.wecom]
enabled = false
corp_id = ""
agent_id = ""
secret = ""

[logging]
level = "INFO"
file_enabled = true
file_path = "logs/heimaclaw.log"
console_enabled = true
EOF
        log_ok "配置文件已创建"
    else
        log_ok "配置文件已存在"
    fi
    
    echo ""
    log_step "创建默认 Agent 模板..."
    if [ ! -d /opt/heimaclaw/data/agents/default ]; then
        mkdir -p /opt/heimaclaw/data/agents/default
        cat > /opt/heimaclaw/data/agents/default/agent.json << 'EOF'
{
  "name": "default",
  "description": "默认助手",
  "enabled": true,
  "llm": {
    "provider": "glm",
    "model_name": "glm-4-flash",
    "api_key": "",
    "temperature": 0.7,
    "max_tokens": 4096
  },
  "channels": [
    {
      "type": "feishu",
      "enabled": false
    }
  ],
  "bindings": {
    "default": true
  },
  "tools": [],
  "sandbox": {
    "enabled": false
  }
}
EOF
        log_ok "默认 Agent 已创建"
    else
        log_ok "默认 Agent 已存在"
    fi
}

# ============================================
# 最终验证
# ============================================
verify() {
    echo ""
    echo "=========================================="
    echo "  安装完成！验证中..."
    echo "=========================================="
    echo ""
    
    if command -v heimaclaw &> /dev/null; then
        log_ok "✅ HeiMaClaw 安装成功!"
        echo ""
        echo "版本信息:"
        heimaclaw --version 2>/dev/null || python3 -m heimaclaw --version 2>/dev/null || echo "  (命令已安装)"
        echo ""
        echo "=========================================="
        echo "  🚀 快速开始"
        echo "=========================================="
        echo ""
        echo "  1. 创建 Agent:"
        echo "     heimaclaw agent create my-agent"
        echo ""
        echo "  2. 配置 SOUL.md:"
        echo "     nano /opt/heimaclaw/data/agents/my-agent/SOUL.md"
        echo ""
        echo "  3. 编译配置:"
        echo "     heimaclaw agent compile my-agent"
        echo ""
        echo "  4. 启动服务:"
        echo "     heimaclaw start"
        echo ""
        echo "=========================================="
        echo ""
        log_ok "🎉 祝你使用愉快!"
        echo ""
    else
        log_error "❌ 安装验证失败，请检查日志"
        return 1
    fi
}

# ============================================
# 主流程
# ============================================
main() {
    # 如果不是 root，给出警告
    if [[ $EUID -ne 0 ]]; then
        log_warn "建议使用 root 用户运行此脚本以获得最佳体验"
        echo ""
    fi
    
    # 捕获错误
    trap 'log_error "安装过程中出错"; exit 1' ERR
    
    # 1. 环境检测
    check_environment || true
    
    # 2. 安装依赖
    install_dependencies || true
    
    # 3. 安装 Python
    install_python || true
    
    # 4. 安装 HeiMaClaw
    install_heimaclaw || true
    
    # 5. 初始化
    init_heimaclaw || true
    
    # 6. 验证
    verify
    
    # 取消错误捕获
    trap - ERR
}

main "$@"
