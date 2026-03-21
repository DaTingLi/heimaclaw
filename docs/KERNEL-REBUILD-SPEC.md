# 内核镜像重新编译规格

**文档版本**: v1.0  
**创建日期**: 2026-03-21  
**状态**: 待执行  
**优先级**: P0 (阻塞沙箱功能)

---

## 1. 问题描述

### 1.1 问题现象
Firecracker microVM 启动时内核 panic：
```
VFS: Cannot open root device "vda" or unknown-block(0,0): error -6
Kernel panic - not syncing: VFS: Unable to mount root fs on unknown-block(0,0)
```

### 1.2 根本原因
内核镜像 `vmlinux` 编译时内置了 `pci=off` 启动参数，导致 virtio-blk 驱动无法正常工作（依赖 PCI 总线）。

### 1.3 影响范围
- 所有启用沙箱的 Agent 无法正常运行
- microVM 无法挂载根文件系统

---

## 2. 解决方案

### 2.1 方案选择
**重新编译内核镜像**，去除内置的 `pci=off` 参数。

### 2.2 编译目标
- 内核版本：5.15.0 (与当前 Ubuntu 宿主机一致)
- 架构：x86_64
- 虚拟化：支持 Firecracker/KVM

### 2.3 必须启用的驱动
| 驱动 | 原因 |
|------|------|
| CONFIG_VIRTIO_BLK | 虚拟硬盘驱动 |
| CONFIG_VIRTIO_NET | 虚拟网络驱动 |
| CONFIG_VIRTIO_MMIO | virtio MMIO 总线 |
| CONFIG_VIRTIO_PCI | virtio PCI 绑定 |
| CONFIG_KVM_GUEST | KVM 客户端支持 |

### 2.4 必须禁用的参数
| 参数 | 原因 |
|------|------|
| pci=off | 禁用 PCI 总线，导致 virtio-blk 失效 |

---

## 3. 编译步骤

### 3.1 准备工作
```bash
# 安装编译依赖
sudo apt update
sudo apt install -y build-essential kernel-package fakeroot libncurses-dev libssl-dev flex bison

# 创建工作目录
mkdir -p ~/kernel-build
cd ~/kernel-build

# 获取内核源码 (5.15.0)
wget https://mirrors.tuna.tsinghua.edu.cn/kernel/v5.x/linux-5.15.tar.xz
tar xf linux-5.15.tar.xz
cd linux-5.15
```

### 3.2 配置内核
```bash
# 复制当前系统配置作为基础
cp /boot/config-5.15.0-119-generic .config

# 使用 menuconfig 调整
make menuconfig

# 关键配置项:
# - Device Drivers -> Virtio drivers -> 全部启用
# - Device Drivers -> Block devices -> Virtio Block Driver -> 启用
# - Processor type and features -> 取消 pci=off 相关配置
```

### 3.3 编译内核
```bash
# 清理
make clean

# 编译 (8 核并行)
make -j8

# 创建 deb 包
make deb-pkg
```

### 3.4 部署新内核
```bash
# 安装 deb 包
sudo dpkg -i linux-image-5.15.0-heimaclaw_*.deb
sudo dpkg -i linux-headers-5.15.0-heimaclaw_*.deb

# 提取 vmlinux
cp /boot/vmlinuz-5.15.0-heimaclaw /opt/heimaclaw/images/vmlinux
```

---

## 4. 验证流程

### 4.1 语法检查
```bash
# 检查内核配置
grep -E "CONFIG_VIRTIO_BLK|CONFIG_PCI" .config
```

### 4.2 启动测试
```bash
# 重启 HeiMaClaw 服务
pkill -f heimaclaw
heimaclaw start

# 检查 microVM 日志
tail -f /opt/heimaclaw/sandboxes/*/stdout.log
```

### 4.3 成功标志
```
[    0.000000] Command line: console=ttyS0 reboot=k panic=1 root=/dev/vda rw
[    1.234567] VFS: mounted root filesystem
```

---

## 5. 回滚方案

### 5.1 回滚步骤
```bash
# 恢复原内核
sudo dpkg -r linux-image-5.15.0-heimaclaw
sudo dpkg -r linux-headers-5.15.0-heimaclaw

# 恢复原 vmlinux
sudo cp /opt/heimaclaw/images/vmlinux.bak /opt/heimaclaw/images/vmlinux

# 重启服务
pkill -f heimaclaw
heimaclaw start
```

### 5.2 备份
```bash
# 备份原 vmlinux
sudo cp /opt/heimaclaw/images/vmlinux /opt/heimaclaw/images/vmlinux.bak
```

---

## 6. 交付物

| 文件 | 位置 | 说明 |
|------|------|------|
| vmlinux | /opt/heimaclaw/images/vmlinux | 新编译的内核镜像 |
| 内核 deb 包 | ~/kernel-build/ | 用于部署到其他机器 |

---

## 7. 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 编译失败 | 时间损失 | 使用已有配置文件 |
| 内核不稳定 | 服务中断 | 先在测试环境验证 |
| 不兼容硬件 | 无法启动 | 虚拟化环境无影响 |

---

**审批人**: 李大婷  
**执行人**: DT@高级开发工程师
