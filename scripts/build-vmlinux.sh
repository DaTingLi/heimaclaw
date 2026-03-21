#!/bin/bash
#==============================================================================
# HeiMaClaw 内核镜像构建脚本
# 
# 功能: 重新编译 Linux 内核镜像，修复 Firecracker 沙箱的 pci=off 问题
# 版本: v1.0
# 日期: 2026-03-21
#==============================================================================

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 日志函数
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 配置变量
KERNEL_VERSION="5.15.0"
KERNEL_SRC_DIR="$HOME/kernel-build/linux-${KERNEL_VERSION}"
KERNEL_BUILD_DIR="$HOME/kernel-build"
OUTPUT_DIR="/opt/heimaclaw/images"
BACKUP_DIR="/opt/heimaclaw/images/backup"
VMLINUX_NAME="vmlinux-heimaclaw"

#==============================================================================
# 准备工作
#==============================================================================
prepare() {
    log_info "=== 准备工作 ==="
    
    # 检查 root 权限
    if [[ $EUID -ne 0 ]]; then
        log_error "需要 root 权限来安装内核包"
        exit 1
    fi
    
    # 创建目录
    mkdir -p "$KERNEL_BUILD_DIR"
    mkdir -p "$BACKUP_DIR"
    
    # 备份原 vmlinux
    if [[ -f "$OUTPUT_DIR/vmlinux" ]]; then
        cp "$OUTPUT_DIR/vmlinux" "$BACKUP_DIR/vmlinux.bak.$(date +%Y%m%d%H%M%S)"
        log_info "已备份原 vmlinux"
    fi
}

#==============================================================================
# 安装编译依赖
#==============================================================================
install_deps() {
    log_info "=== 安装编译依赖 ==="
    apt update
    apt install -y \
        build-essential \
        # kernel-package (removed - not available in Ubuntu 24.04) \
        fakeroot \
        libncurses-dev \
        libssl-dev \
        flex \
        bison \
        libelf-dev \
        dwarves \
        zstd
}

#==============================================================================
# 下载内核源码
#==============================================================================
download_kernel() {
    log_info "=== 下载内核源码 ==="
    
    if [[ -d "$KERNEL_SRC_DIR" ]]; then
        log_warn "内核源码已存在，跳过下载"
        return
    fi
    
    cd "$KERNEL_BUILD_DIR"
    
    # 使用清华镜像
    # 使用 Ubuntu 内核源码
    cp /usr/src/linux-source-5.15.0.tar.bz2 "${KERNEL_BUILD_DIR}/linux-${KERNEL_VERSION}.tar.xz"
    
    tar xjf "linux-${KERNEL_VERSION}.tar.xz"
    
    log_info "内核源码已解压到 $KERNEL_SRC_DIR"
}

#==============================================================================
# 配置内核
#==============================================================================
configure_kernel() {
    log_info "=== 配置内核 ==="
    
    cd "$KERNEL_SRC_DIR"
    
    # 复制当前系统配置
    cp /boot/config-$(uname -r) .config 2>/dev/null || \
    cp /boot/config-5.15.0-119-generic .config
    
    # 更新配置以匹配新内核版本
    yes "" | make oldconfig
    
    log_info "内核配置已更新"
}

#==============================================================================
# 修改内核配置 (去除 pci=off)
#==============================================================================
modify_config() {
    log_info "=== 修改内核配置 ==="
    
    cd "$KERNEL_SRC_DIR"
    
    # 使用 menuconfig 进行交互式配置 (需要图形界面)
    # 或者使用脚本方式修改
    
    # 确保 virtio 驱动启用
    sed -i 's/CONFIG_VIRTIO_BLK=m/CONFIG_VIRTIO_BLK=y/' .config
    sed -i 's/CONFIG_VIRTIO_NET=m/CONFIG_VIRTIO_NET=y/' .config
    sed -i 's/CONFIG_VIRTIO_MMIO=m/CONFIG_VIRTIO_MMIO=y/' .config
    sed -i 's/CONFIG_VIRTIO_PCI=m/CONFIG_VIRTIO_PCI=y/' .config
    sed -i 's/CONFIG_KVM_GUEST=m/CONFIG_KVM_GUEST=y/' .config

    # 确保 VSOCK 驱动启用 (内置)
    sed -i 's/CONFIG_VSOCKETS=m/CONFIG_VSOCKETS=y/' .config
    sed -i 's/# CONFIG_VSOCKETS is not set/CONFIG_VSOCKETS=y/' .config
    sed -i 's/CONFIG_VIRTIO_VSOCKETS=m/CONFIG_VIRTIO_VSOCKETS=y/' .config
    sed -i 's/# CONFIG_VIRTIO_VSOCKETS is not set/CONFIG_VIRTIO_VSOCKETS=y/' .config
    sed -i 's/CONFIG_VHOST_VSOCK=m/CONFIG_VHOST_VSOCK=y/' .config
    sed -i 's/# CONFIG_VHOST_VSOCK is not set/CONFIG_VHOST_VSOCK=y/' .config
    
    # 确保 PCI 支持启用
    sed -i 's/CONFIG_PCI=n/CONFIG_PCI=y/' .config
    sed -i 's/CONFIG_PCI_MSI=y/# CONFIG_PCI_MSI is not set/' .config 2>/dev/null || true
    
    # 移除可能内置的 pci=off
    # 在 .config 中查找并注释相关行
    sed -i 's/CONFIG_CMDLINE=".*pci=off.*"/# CONFIG_CMDLINE is not set/' .config
    
    # 确保没有内置命令行包含 pci=off
    echo "CONFIG_CMDLINE=\"console=ttyS0 reboot=k panic=1\"" >> .config
    
    log_info "内核配置已修改，virtio 驱动已启用"
}

#==============================================================================
# 编译内核
#==============================================================================
build_kernel() {
    log_info "=== 编译内核 ==="
    log_info "这可能需要 15-30 分钟..."
    
    cd "$KERNEL_SRC_DIR"
    
    # 获取 CPU 核数
    NPROC=$(nproc)
    log_info "使用 $NPROC 核并行编译"
    
    # 清理
    make clean
    
    # 编译
    time make -j${NPROC}
    
    # 创建 deb 包
    time make deb-pkg KDEB_PKGVERSION=heimaclaw.1 LOCALVERSION=-heimaclaw
    
    log_info "内核编译完成"
}

#==============================================================================
# 部署内核
#==============================================================================
deploy_kernel() {
    log_info "=== 部署内核 ==="
    
    cd "$KERNEL_BUILD_DIR"
    
    # 安装 deb 包
    dpkg -i linux-image-*.deb 2>/dev/null || true
    dpkg -i linux-headers-*.deb 2>/dev/null || true
    
    # 查找并复制新内核
    NEW_VMLINUZ=$(ls /boot/vmlinuz-*heimaclaw 2>/dev/null | head -1)
    
    if [[ -n "$NEW_VMLINUZ" ]]; then
        # vmlinuz 是压缩内核，需要解压为 vmlinux
        cat "$NEW_VMLINUZ" > "$OUTPUT_DIR/vmlinux"
        log_info "新内核已部署到 $OUTPUT_DIR/vmlinux"
    else
        log_error "未找到编译的内核镜像"
        exit 1
    fi
}

#==============================================================================
# 验证
#==============================================================================
verify() {
    log_info "=== 验证内核 ==="
    
    # 检查文件
    if [[ ! -f "$OUTPUT_DIR/vmlinux" ]]; then
        log_error "vmlinux 文件不存在"
        exit 1
    fi
    
    # 检查文件大小
    SIZE=$(stat -c%s "$OUTPUT_DIR/vmlinux")
    if [[ $SIZE -lt 50000000 ]]; then
        log_error "vmlinux 文件太小，可能不完整"
        exit 1
    fi
    
    log_info "vmlinux 大小: $(du -h $OUTPUT_DIR/vmlinux | cut -f1)"
    
    # 检查内核版本
    strings "$OUTPUT_DIR/vmlinux" | grep -E "Linux version [0-9]" | head -1
}

#==============================================================================
# 主函数
#==============================================================================
main() {
    log_info "HeiMaClaw 内核镜像构建脚本"
    log_info "目标: 修复 Firecracker 沙箱 pci=off 问题"
    
    case "${1:-all}" in
        prepare)
            prepare
            install_deps
            download_kernel
            ;;
        configure)
            configure_kernel
            modify_config
            ;;
        build)
            build_kernel
            ;;
        deploy)
            deploy_kernel
            ;;
        verify)
            verify
            ;;
        all)
            prepare
            install_deps
            download_kernel
            configure_kernel
            modify_config
            build_kernel
            deploy_kernel
            verify
            log_info "=== 完成 ==="
            ;;
        help|--help|-h)
            echo "用法: $0 [prepare|configure|build|deploy|verify|all]"
            echo ""
            echo "  prepare    - 准备工作 (安装依赖, 下载源码)"
            echo "  configure  - 配置内核"
            echo "  build      - 编译内核"
            echo "  deploy     - 部署内核"
            echo "  verify     - 验证部署"
            echo "  all        - 执行全部步骤 (默认)"
            ;;
        *)
            log_error "未知参数: $1"
            echo "使用 '$0 help' 查看帮助"
            exit 1
            ;;
    esac
}

main "$@"
