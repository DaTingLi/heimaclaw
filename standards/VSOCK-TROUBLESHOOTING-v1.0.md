# VSOCK 通信问题排查与修复

**日期**: 2026-03-22  
**问题**: Firecracker microVM 沙箱 vsock 通信失败  
**状态**: ✅ 已解决

---

## 问题现象

1. 飞书机器人发送 `cat /tmp/heimaclaw_test_code.txt` 命令
2. VM 返回 "文件不存在" 或命令执行无响应
3. 系统自动降级到本地执行（fallback）

---

## 排查过程

### 1. 检查 vsock 连接状态
```
宿主机 → CONNECT 1234 → Firecracker
宿主机 ← OK <port> ← Firecracker
```
握手成功，但后续命令无响应。

### 2. 检查 VM 内部 vsock server 日志
```
Starting HeiMaClaw vsock-server...
vsock-server started (PID: 118)
/bin/sh: can't access tty; job control turned off
~ # vsock 服务端启动: port=1234
```
vsock server 启动成功，但没有处理任何命令。

### 3. 错误假设
误以为 VM 需要处理 CONNECT 握手，在 `server.py` 中添加了：
```python
# 错误的代码
handshake_data = b""
while b"\n" not in handshake_data:
    chunk = conn.recv(1)
    handshake_data += chunk

if handshake_data.startswith(b"CONNECT "):
    conn.sendall(b"OK\n")
```

### 4. 根本原因发现
根据 Firecracker vsock 文档：

> Host: `connect()` to AF_UNIX at `uds_path`.  
> Host: `send()` "CONNECT `<port_num>`\\n".  
> Guest: `accept()` the new connection.  
> Host: `read()` "OK `<assigned_hostside_port>`\\n".

**关键点**: CONNECT 命令由 **Firecracker vsock 代理自动处理**，不会转发给 VM！

VM 的 `accept()` 返回后，直接进行数据通信（4字节长度 + JSON），**不需要也不应该尝试读取 CONNECT**。

### 5. 修复方案
恢复原始 `vsock/server.py` 代码，不做任何 CONNECT 握手处理：

```python
# 正确的代码（原始）
def _handle_connection(self, conn, addr):
    try:
        while True:
            # 直接读取命令数据
            length_data = self._recv_exact(conn, 4)
            if not length_data:
                break
            length = struct.unpack(">I", length_data)[0]
            data = self._recv_exact(conn, length)
            # 处理命令...
```

---

## 经验教训

### 1. Firecracker vsock 架构
```
宿主机 (Unix Socket) ←→ Firecracker (vsock 代理) ←→ VM (AF_VSOCK)
                            ↓
                     自动处理 CONNECT 握手
```

### 2. 正确的开发流程
1. 先阅读官方文档
2. 理解架构后再修改代码
3. 写测试用例验证

### 3. 降级机制（fallback）的影响
当 vsock 失败时，系统自动降级到本地执行：
- 工作目录变成 `./heimaclaw_workspace`（宿主机）
- 与沙箱内 `/tmp/` 隔离
- 导致文件找不到的"幻觉"

### 4. 测试文件位置
- **模板 rootfs**: `/opt/heimaclaw/images/rootfs.ext4`
- **每个沙箱**: `/opt/heimaclaw/sandboxes/<instance_id>/rootfs.ext4`（独立副本）
- 修改模板不会自动更新已有沙箱

---

## 代码变更

### `src/heimaclaw/sandbox/vsock/server.py`
- 移除了错误的 CONNECT 握手处理代码
- 恢复为直接读取 4 字节长度 + JSON 的原始逻辑

### 相关文件
- `src/heimaclaw/agent/firecracker_deepagents_backend.py` - 沙箱执行后端
- `src/heimaclaw/sandbox/firecracker.py` - Firecracker 实例管理
- `src/heimaclaw/agent/deepagents_wrapper.py` - DeepAgents 包装器

---

## 验证方法

```bash
# 1. 重启服务
pkill -f "heimaclaw start"
cd /root/dt/ai_coding/heimaclaw
/usr/bin/python3.12 /usr/local/bin/heimaclaw start

# 2. 测试 vsock 通信
python3 << 'PYEOF'
import socket, json, struct

vsock_path = "/opt/heimaclaw/sandboxes/<instance_id>/vsock.sock"
sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
sock.connect(vsock_path)

sock.sendall(b"CONNECT 1234\n")
resp = b""
while b"\n" not in resp:
    resp += sock.recv(1)

request = {"type": "execute", "command": "echo hello", "timeout_ms": 5000}
data = json.dumps(request).encode()
sock.sendall(struct.pack(">I", len(data)))
sock.sendall(data)

len_data = sock.recv(4)
resp_len = struct.unpack(">I", len_data)[0]
resp_data = b""
while len(resp_data) < resp_len:
    resp_data += sock.recv(resp_len - len(resp_data))

print(json.loads(resp_data))
sock.close()
PYEOF
```

---

## 预防措施

1. **不要修改 vsock server 握手逻辑** - Firecracker 代理会处理
2. **使用 fallback 模式时注意工作目录** - 与沙箱隔离
3. **更新 rootfs 后需要重启所有沙箱实例**
4. **添加更详细的沙箱日志** - 便于排查问题

---

**Author**: DT@高级开发工程师  
**Reviewer**: 李大婷
