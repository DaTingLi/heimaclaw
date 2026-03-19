#!/bin/bash
set -e

# ============================================
# HeiMaClaw 一键安装脚本
# ============================================
# 支持: Ubuntu 18.04+, Debian 10+, CentOS 8+
# Python: 3.10+
# ============================================

set -e

echo "=========================================="
echo "  HeiMaClaw 一键安装脚本 v1.0"
echo "=========================================="

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 检查是否为 root
if [[ $EUID -ne 0 ]]; then
   log_warn "建议使用 root 用户运行此脚本"
fi

# 1. 检测并安装 Python
install_python() {
    log_info "检查 Python 环境..."
    
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
        log_info "检测到 Python $PYTHON_VERSION"
        
        if [[ $(echo "$PYTHON_VERSION >= 3.10" | bc -l) -eq 0 ]]; then
            log_error "Python 版本需要 >= 3.10，当前: $PYTHON_VERSION"
            log_info "正在安装 Python 3.10..."
            install_python_apt
        fi
    else
        log_warn "未检测到 Python，正在安装..."
        install_python_apt
    fi
    
    # 验证 pip
    if ! command -v pip3 &> /dev/null; then
        log_info "安装 pip..."
        apt-get install -y python3-pip
    fi
    
    log_info "Python 环境准备完成"
}

install_python_apt() {
    # Ubuntu/Debian
    if command -v apt-get &> /dev/null; then
        apt-get update
        apt-get install -y software-properties-common
        add-apt-repository -y ppa:deadsnakes/ppa
        apt-get update
        apt-get install -y python3.10 python3.10-venv python3.10-dev python3-pip
        update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1
        update-alternatives --install /usr/bin/pip3 pip3 /usr/bin/pip3 1
    # CentOS/RHEL
    elif command -v yum &> /dev/null; then
        yum install -y python3.10
    fi
}

# 2. 安装 HeiMaClaw
install_heimaclaw() {
    log_info "安装 HeiMaClaw..."
    
    # 优先使用 pip 安装
    if [ -f "./dist/heimaclaw-0.1.0-py3-none-any.whl" ]; then
        log_info "使用本地 wheel 安装..."
        pip3 install ./dist/heimaclaw-0.1.0-py3-none-any.whl
    else
        # 从 PyPI 安装（未来发布后启用）
        # pip3 install heimaclaw
        log_error "请先构建 wheel: pip install build && python -m build"
        exit 1
    fi
    
    log_info "HeiMaClaw 安装完成"
}

# 3. 初始化
init_heimaclaw() {
    log_info "初始化 HeiMaClaw..."
    
    heimaclaw init
    
    log_info "初始化完成!"
}

# 4. 验证安装
verify() {
    log_info "验证安装..."
    
    if command -v heimaclaw &> /dev/null; then
        echo ""
        log_info "✅ HeiMaClaw 安装成功!"
        echo ""
        echo "版本信息:"
        heimaclaw --version
        echo ""
        echo "快速开始:"
        echo "  1. heimaclaw agent create my-agent  # 创建 Agent"
        echo "  2. heimaclaw agent compile my-agent # 编译"
        echo "  3. heimaclaw start                 # 启动"
        echo ""
    else
        log_error "安装验证失败"
        exit 1
    fi
}

# 主流程
main() {
    install_python
    install_heimaclaw
    init_heimaclaw
    verify
    
    log_info "全部完成! 🎉"
}

main "$@"
