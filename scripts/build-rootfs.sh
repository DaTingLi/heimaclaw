#!/bin/bash
# 构建 HeiMaClaw microVM rootfs
# 包含 vsock 服务端和 Python 运行时

set -e

ROOTFS_DIR=${1:-"/opt/heimaclaw/images/rootfs"}
ROOTFS_SIZE=${2:-256}  # MB
ALPINE_VER="3.19"

echo "=== 构建 HeiMaClaw rootfs ==="
echo "目录: $ROOTFS_DIR"
echo "大小: ${ROOTFS_SIZE}MB"

# 创建空文件系统
dd if=/dev/zero of=/tmp/heimaclaw-rootfs.ext4 bs=1M count=$ROOTFS_SIZE
mkfs.ext4 /tmp/heimaclaw-rootfs.ext4

# 挂载
mkdir -p /mnt/heimaclaw-rootfs
mount -o loop /tmp/heimaclaw-rootfs.ext4 /mnt/heimaclaw-rootfs

# 下载并解压 Alpine rootfs
cd /tmp
curl -fsSL "https://dl-cdn.alpinelinux.org/alpine/v${ALPINE_VER}/releases/x86_64/alpine-minirootfs-${ALPINE_VER}.1-x86_64.tar.gz" -o alpine.tgz
tar xzf alpine.tgz -C /mnt/heimaclaw-rootfs

# 安装 Python
chroot /mnt/heimaclaw-rootfs /sbin/apk add --no-cache python3 py3-pip

# 创建 HeiMaClaw 目录
mkdir -p /mnt/heimaclaw-rootfs/opt/heimaclaw/lib/python
mkdir -p /mnt/heimaclaw-rootfs/opt/heimaclaw/tools
mkdir -p /mnt/heimaclaw-rootfs/opt/heimaclaw/data

# 复制 vsock 服务端
cp src/heimaclaw/sandbox/vsock/*.py /mnt/heimaclaw-rootfs/opt/heimaclaw/lib/python/heimaclaw/sandbox/vsock/
cp src/heimaclaw/sandbox/vsock_agent.py /mnt/heimaclaw-rootfs/opt/heimaclaw/bin/heimaclaw-vsock-agent
chmod +x /mnt/heimaclaw-rootfs/opt/heimaclaw/bin/heimaclaw-vsock-agent

# 复制 console 模块（服务端依赖）
mkdir -p /mnt/heimaclaw-rootfs/opt/heimaclaw/lib/python/heimaclaw
cp src/heimaclaw/__init__.py /mnt/heimaclaw-rootfs/opt/heimaclaw/lib/python/heimaclaw/
cp src/heimaclaw/console.py /mnt/heimaclaw-rootfs/opt/heimaclaw/lib/python/heimaclaw/

# 创建 init 脚本
cat > /mnt/heimaclaw-rootfs/init << 'INIT'
#!/bin/sh
# HeiMaClaw microVM init

mount -t proc none /proc
mount -t sysfs none /sys
mount -t devtmpfs none /dev

echo "=== HeiMaClaw microVM ==="
echo "启动 vsock 服务端..."

# 启动 vsock 服务端
export PYTHONPATH=/opt/heimaclaw/lib/python
python3 /opt/heimaclaw/bin/heimaclaw-vsock-agent --port 1234 &

echo "vsock 服务端已启动 (port=1234)"
echo "进入交互模式..."

exec /bin/sh
INIT

chmod +x /mnt/heimaclaw-rootfs/init

# 卸载
sync
umount /mnt/heimaclaw-rootfs

# 移动到目标位置
mv /tmp/heimaclaw-rootfs.ext4 "$ROOTFS_DIR"

echo "=== rootfs 构建完成 ==="
echo "文件: $ROOTFS_DIR"
ls -lh "$ROOTFS_DIR"
