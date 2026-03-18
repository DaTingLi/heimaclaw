# HeiMaClaw 生产部署指南

## 1. 安装

```bash
# 从源码安装
cd /root/dt/ai_coding/heimaclaw
python -m venv venv
source venv/bin/activate
pip install -e .

# 或从 PyPI 安装
pip install heimaclaw
```

## 2. 初始化

```bash
# 初始化项目目录
heimaclaw init

# 查看配置
heimaclaw config show
```

## 3. 配置渠道

### 飞书

```bash
heimaclaw config set channels.feishu.enabled true
heimaclaw config set channels.feishu.app_id YOUR_APP_ID
heimaclaw config set channels.feishu.app_secret YOUR_APP_SECRET
```

### 企业微信

```bash
heimaclaw config set channels.wecom.enabled true
heimaclaw config set channels.wecom.corp_id YOUR_CORP_ID
heimaclaw config set channels.wecom.agent_id YOUR_AGENT_ID
heimaclaw config set channels.wecom.secret YOUR_SECRET
```

## 4. 创建 Agent

```bash
# 创建 Agent
heimaclaw agent create my-agent

# 编辑 Agent 配置
heimaclaw config edit
```

## 5. 安装工具

```bash
# 创建工具
heimaclaw tool create my-tool

# 安装工具
heimaclaw tool install /path/to/heimaclaw-tool-my-tool

# 查看已安装工具
heimaclaw tool list
```

## 6. systemd 服务部署

```bash
# 复制服务文件
sudo cp deploy/heimaclaw.service /etc/systemd/system/

# 重新加载 systemd
sudo systemctl daemon-reload

# 启动服务
sudo systemctl start heimaclaw

# 查看状态
sudo systemctl status heimaclaw

# 开机自启
sudo systemctl enable heimaclaw

# 查看日志
sudo journalctl -u heimaclaw -f
```

## 7. 监控和统计

### API 端点

```bash
# 健康检查
curl http://localhost:8000/health

# Token 使用统计
curl http://localhost:8000/api/monitoring/token-stats

# 每日使用量
curl http://localhost:8000/api/monitoring/daily-usage

# Agent 使用统计
curl http://localhost:8000/api/monitoring/agent-usage/default
```

### CLI 命令

```bash
# Token 统计
heimaclaw monitoring token-stats

# 过滤 Agent
heimaclaw monitoring token-stats --agent default

# 过滤提供商
heimaclaw monitoring token-stats --provider glm

# 查看最近 30 天
heimaclaw monitoring token-stats --days 30

# 每日使用量
heimaclaw monitoring daily-usage --days 7

# 清理旧记录
heimaclaw monitoring clear-old --days 90
```

## 8. 日志管理

日志文件位置：`/opt/heimaclaw/logs/heimaclaw.log`

### 日志轮转配置

创建 `/etc/logrotate.d/heimaclaw`:

```
/opt/heimaclaw/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0640 root root
}
```

## 9. 性能调优

### 服务参数

```bash
# 多 worker
heimaclaw start --workers 4

# 自定义端口
heimaclaw start --port 8080
```

### 资源限制

编辑 `/etc/systemd/system/heimaclaw.service`:

```ini
[Service]
# 内存限制
MemoryMax=2G

# CPU 限制
CPUQuota=200%

# 文件描述符限制
LimitNOFILE=65535
```

## 10. 故障排查

```bash
# 检查环境
heimaclaw doctor

# 查看服务状态
systemctl status heimaclaw

# 查看日志
journalctl -u heimaclaw -n 100

# 测试 API
curl http://localhost:8000/health
```

## 11. 备份和恢复

### 备份

```bash
# 备份配置和数据
tar czf heimaclaw-backup.tar.gz /opt/heimaclaw/config /opt/heimaclaw/data
```

### 恢复

```bash
tar xzf heimaclaw-backup.tar.gz -C /
systemctl restart heimaclaw
```

## 12. 安全建议

1. 使用 HTTPS（配置反向代理）
2. 限制 API 访问（防火墙规则）
3. 定期更新依赖
4. 保护 API Key 和 Secret
5. 启用日志审计

## 13. Nginx 反向代理配置

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 14. vsock 服务端集成

### 更新 rootfs

```bash
# 方式1: 使用更新脚本（在项目目录执行）
cd /root/dt/ai_coding/heimaclaw
./scripts/update-rootfs.sh

# 方式2: 从头构建
./scripts/build-rootfs.sh /opt/heimaclaw/images/rootfs.ext4 256
```

### rootfs 目录结构

```
/opt/heimaclaw/images/
├── vmlinux           # Linux kernel
└── rootfs.ext4       # Alpine rootfs + vsock 服务端
    /opt/heimaclaw/
    ├── lib/python/heimaclaw/  # Python 模块
    │   ├── __init__.py
    │   ├── console.py
    │   └── sandbox/vsock/
    │       ├── __init__.py
    │       ├── client.py
    │       ├── server.py
    │       └── manager.py
    └── bin/
        └── vsock-server        # vsock 服务端启动脚本

/init                # microVM 启动脚本
```

### vsock 通信流程

```
1. Firecracker 启动 microVM
2. init 脚本自动启动 vsock-server
3. vsock-server 监听 CID:1234
4. 宿主机通过 vsock.sock 连接
5. 发送命令执行请求
6. 接收执行结果
```

### 测试 vsock 通信

```python
# 在宿主机执行
from heimaclaw.sandbox.vsock import VsockClient

# CID 从 instance info 获取
client = VsockClient(cid=10000, port=1234)
client.connect()

# 测试命令执行
result = client.send_command("execute", {
    "command": "uname -a"
})
print(result)

client.disconnect()
```

### vsock 服务端命令

microVM 内的 vsock 服务端支持以下命令类型：

| 类型 | 功能 | 示例 |
|------|------|------|
| execute | 执行 shell 命令 | `{"type":"execute","command":"ls"}` |
| health_check | 健康检查 | `{"type":"health_check"}` |
| get_info | 查询系统信息 | `{"type":"get_info"}` |

### 故障排查

```bash
# 检查 vsock 内核模块
lsmod | grep vsock

# 检查 /dev/vhost-vsock
ls -la /dev/vhost-vsock

# 查看 microVM 日志
cat /opt/heimaclaw/sandboxes/<instance_id>/stdout.log

# 测试 vsock 连接
python3 -c "
from heimaclaw.sandbox.vsock import VsockClient
c = VsockClient(10000, 1234)
c.connect()
print(c.send_command('health_check'))
c.disconnect()
"
```
