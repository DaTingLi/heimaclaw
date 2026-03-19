#!/bin/bash
set -e

# ============================================
# HeiMaClaw 一键安装脚本 v2.0
# ============================================
# 支持: Ubuntu 18.04+, Debian 10+, CentOS 8+
# Python: 3.10+
# ============================================

set -e

echo "=========================================="
echo "  HeiMaClaw 一键安装脚本 v2.0"
echo "=========================================="
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_check() { echo -e "${BLUE}[CHECK]${NC} $1"; }

# ============================================
# 环境检测
# ============================================
check_environment() {
    echo "=========================================="
    echo "  第一步：环境检测"
    echo "=========================================="
    echo ""
    
    local all_passed=true
    
    # 1. 检测操作系统
    log_check "检测操作系统..."
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        log_info "操作系统: $NAME $VERSION"
        if [[ "$ID" == "ubuntu" ]] || [[ "$ID" == "debian" ]] || [[ "$ID" == "centos" ]] || [[ "$ID" == "rhel" ]]; then
            log_info "✅ 支持的操作系统"
        else
            log_warn "未测试的操作系统: $ID"
        fi
    else
        log_warn "无法检测操作系统"
    fi
    echo ""
    
    # 2. 检测 Python
    log_check "检测 Python 环境..."
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
        PYTHON_FULL=$(python3 --version)
        log_info "检测到: $PYTHON_FULL"
        
        # 检查版本
        if command -v bc &> /dev/null; then
            if [[ $(echo "$PYTHON_VERSION >= 3.10" | bc -l) -eq 1 ]]; then
                log_info "✅ Python 版本满足要求 (>= 3.10)"
            else
                log_error "❌ Python 版本过低: $PYTHON_VERSION (需要 >= 3.10)"
                all_passed=false
            fi
        else
            # 简单检查
            PYTHON_MAJOR=$(python3 -c 'import sys; print(sys.version_info[0])')
            PYTHON_MINOR=$(python3 -c 'import sys; print(sys.version_info[1])')
            if [[ $PYTHON_MAJOR -gt 3 ]] || [[ $PYTHON_MAJOR -eq 3 && $PYTHON_MINOR -ge 10 ]]; then
                log_info "✅ Python 版本满足要求"
            else
                log_error "❌ Python 版本过低: $PYTHON_VERSION (需要 >= 3.10)"
                all_passed=false
            fi
        fi
    else
        log_error "❌ 未检测到 Python3"
        all_passed=false
    fi
    echo ""
    
    # 3. 检测 pip
    log_check "检测 pip..."
    if command -v pip3 &> /dev/null; then
        PIP_VERSION=$(pip3 --version | cut -d' ' -f2)
        log_info "检测到 pip: $PIP_VERSION"
        log_info "✅ pip 已安装"
    else
        log_error "❌ 未检测到 pip3"
        all_passed=false
    fi
    echo ""
    
    # 4. 检测端口
    log_check "检测端口 8000..."
    if command -v nc &> /dev/null; then
        if nc -z localhost 8000 2>/dev/null; then
            log_warn "⚠️ 端口 8000 已被占用"
            log_info "   HeiMaClaw 可使用其他端口: heimaclaw start --port 8080"
        else
            log_info "✅ 端口 8000 可用"
        fi
    else
        log_warn "无法检测端口 (netcat 未安装)"
    fi
    echo ""
    
    # 5. 检测 Firecracker (可选)
    log_check "检测 Firecracker (可选)..."
    if command -v firecracker &> /dev/null; then
        FC_VERSION=$(firecracker --version 2>&1 | head -1)
        log_info "✅ Firecracker 已安装: $FC_VERSION"
    else
        log_warn "⚠️ Firecracker 未安装 (沙箱隔离功能不可用)"
        log_info "   如需安装: https://github.com/firecracker-microvm/firecracker"
    fi
    echo ""
    
    # 6. 检测 KVM (可选)
    log_check "检测 KVM 虚拟化 (可选)..."
    if [[ -e /dev/kvm ]]; then
        log_info "✅ KVM 已启用 (硬件虚拟化支持)"
    else
        log_warn "⚠️ KVM 不可用 (沙箱将使用降级模式)"
    fi
    echo ""
    
    # 总结
    echo "=========================================="
    echo "  环境检测结果"
    echo "=========================================="
    if $all_passed; then
        log_info "✅ 所有必需环境已就绪!"
        echo ""
        return 0
    else
        log_error "❌ 部分环境未就绪，请先安装依赖"
        echo ""
        return 1
    fi
}

# ============================================
# 安装 Python 3.10 (如果需要)
# ============================================
install_python_if_needed() {
    echo "=========================================="
    echo "  第二步：安装/升级 Python"
    echo "=========================================="
    echo ""
    
    PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    
    # 检查版本
    PYTHON_MAJOR=$(python3 -c 'import sys; print(sys.version_info[0])')
    PYTHON_MINOR=$(python3 -c 'import sys; print(sys.version_info[1])')
    
    if [[ $PYTHON_MAJOR -gt 3 ]] || [[ $PYTHON_MAJOR -eq 3 && $PYTHON_MINOR -ge 10 ]]; then
        log_info "Python 版本已满足要求，跳过安装"
        echo ""
        return 0
    fi
    
    log_info "安装 Python 3.10..."
    
    if command -v apt-get &> /dev/null; then
        # Ubuntu/Debian
        apt-get update
        apt-get install -y software-properties-common
        add-apt-repository -y ppa:deadsnakes/ppa 2>/dev/null || true
        apt-get update
        apt-get install -y python3.10 python3.10-venv python3.10-dev python3-pip
        update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1 2>/dev/null || true
        log_info "✅ Python 3.10 安装完成"
    elif command -v yum &> /dev/null; then
        # CentOS/RHEL
        yum install -y python3.10
        log_info "✅ Python 3.10 安装完成"
    else
        log_error "无法安装 Python，请手动安装 Python 3.10+"
        return 1
    fi
    
    echo ""
}

# ============================================
# 安装 HeiMaClaw
# ============================================
install_heimaclaw() {
    echo "=========================================="
    echo "  第三步：安装 HeiMaClaw"
    echo "=========================================="
    echo ""
    
    # 检查是否有 wheel 文件
    if [ -f "./dist/heimaclaw-0.1.0-py3-none-any.whl" ]; then
        log_info "使用本地 wheel 安装..."
        pip3 install ./dist/heimaclaw-0.1.0-py3-none-any.whl
    else
        log_info "使用 PyPI 安装 (需网络)..."
        pip3 install heimaclaw
    fi
    
    log_info "✅ HeiMaClaw 安装完成"
    echo ""
}

# ============================================
# 初始化
# ============================================
init_heimaclaw() {
    echo "=========================================="
    echo "  第四步：初始化"
    echo "=========================================="
    echo ""
    
    log_info "初始化项目..."
    heimaclaw init --path /opt/heimaclaw 2>/dev/null || heimaclaw init || true
    log_info "✅ 初始化完成"
    echo ""
}

# ============================================
# 最终验证
# ============================================
verify() {
    echo "=========================================="
    echo "  最终验证"
    echo "=========================================="
    echo ""
    
    if command -v heimaclaw &> /dev/null; then
        log_info "✅ HeiMaClaw 安装成功!"
        echo ""
        echo "版本信息:"
        heimaclaw --version
        echo ""
        echo "环境诊断:"
        heimaclaw doctor
        echo ""
        echo "快速开始:"
        echo "  1. heimaclaw agent create my-agent    # 创建 Agent"
        echo "  2. heimaclaw agent compile my-agent   # 编译配置"
        echo "  3. heimaclaw start                   # 启动服务 (端口 8000)"
        echo ""
        echo "常用命令:"
        echo "  heimaclaw agent list                  # 列出所有 Agent"
        echo "  heimaclaw config show                 # 查看配置"
        echo "  heimaclaw status                      # 查看状态"
        echo ""
        return 0
    else
        log_error "❌ 安装验证失败"
        return 1
    fi
}

# ============================================
# 主流程
# ============================================
main() {
    # 检查是否 root
    if [[ $EUID -ne 0 ]]; then
        log_warn "建议使用 root 用户运行此脚本"
        echo ""
    fi
    
    # 1. 环境检测
    if ! check_environment; then
        log_warn "环境检测未完全通过，继续安装..."
    fi
    
    # 2. 安装 Python
    install_python_if_needed
    
    # 3. 安装 HeiMaClaw
    install_heimaclaw
    
    # 4. 初始化
    init_heimaclaw
    
    # 5. 验证
    verify
    
    echo "=========================================="
    log_info "🎉 安装完成!"
    echo "=========================================="
}

main "$@"
