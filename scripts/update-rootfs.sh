#!/bin/bash
# 更新现有 rootfs，添加 vsock 服务端

set -e

ROOTFS="/opt/heimaclaw/images/rootfs.ext4"
MOUNT_DIR="/mnt/heimaclaw-rootfs"

echo "=== 更新 rootfs ==="

# 挂载 rootfs
mkdir -p "$MOUNT_DIR"
mount -o loop "$ROOTFS" "$MOUNT_DIR"

# 创建目录
mkdir -p "$MOUNT_DIR/opt/heimaclaw/lib/python/heimaclaw/sandbox/vsock"
mkdir -p "$MOUNT_DIR/opt/heimaclaw/bin"

# 复制文件
cp src/heimaclaw/__init__.py "$MOUNT_DIR/opt/heimaclaw/lib/python/heimaclaw/"
cp src/heimaclaw/console.py "$MOUNT_DIR/opt/heimaclaw/lib/python/heimaclaw/"
cp src/heimaclaw/sandbox/vsock/*.py "$MOUNT_DIR/opt/heimaclaw/lib/python/heimaclaw/sandbox/vsock/"

# 创建启动脚本
cat > "$MOUNT_DIR/opt/heimaclaw/bin/vsock-server" << 'SCRIPT'
#!/usr/bin/env python3
import sys
sys.path.insert(0, "/opt/heimaclaw/lib/python")
from heimaclaw.sandbox.vsock.server import main
main()
SCRIPT
chmod +x "$MOUNT_DIR/opt/heimaclaw/bin/vsock-server"

# 更新 init
cat > "$MOUNT_DIR/init" << 'INIT'
#!/bin/sh
mount -t proc none /proc
mount -t sysfs none /sys
mount -t devtmpfs none /dev

echo "=== HeiMaClaw microVM ==="
export PYTHONPATH=/opt/heimaclaw/lib/python
/opt/heimaclaw/bin/vsock-server --port 1234 &
echo "vsock 服务端已启动"
exec /bin/sh
INIT
chmod +x "$MOUNT_DIR/init"

# 卸载
sync
umount "$MOUNT_DIR"

echo "=== rootfs 更新完成 ==="
