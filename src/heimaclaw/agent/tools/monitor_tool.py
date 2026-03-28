"""
Monitor 监控工具

提供容器资源监控和告警功能。
用户说话就能用：现在容器状态怎么样、帮我看看内存使用
"""

from typing import Any

from heimaclaw.console import info, error

# 工具定义
MONITOR_TOOL_DEFINITION = {
    "name": "docker_monitor",
    "description": """Docker 容器监控工具 - 查看容器资源使用情况和告警

用途：
- 查看容器状态（运行中/已停止/空闲）
- 查看资源使用（CPU、内存）
- 查看端口占用情况
- 主动告警（资源超限时通知）

使用场景：
- 用户说"现在容器状态怎么样" → 调用 monitor_status
- 用户说"帮我看看内存使用" → 调用 monitor_stats
- 系统检测到资源超限 → 自动调用 monitor_alert""",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "操作类型: status(容器状态), stats(资源统计), inspect(单个详情), alert(资源告警)",
                "enum": ["status", "stats", "inspect", "alert"]
            },
            "project_name": {
                "type": "string",
                "description": "项目名称（用于 inspect）"
            }
        },
        "required": ["action"]
    }
}


def monitor_handler(args: dict) -> dict:
    """
    监控工具处理器
    """
    import subprocess
    import json
    
    action = args.get("action")
    project_name = args.get("project_name")
    
    try:
        if action == "status":
            # 获取所有容器状态
            result = subprocess.run(
                ["docker", "ps", "-a", "--format", "{{.Names}}|{{.Status}}|{{.Ports}}"],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode != 0:
                return {
                    "success": False,
                    "error": "获取容器状态失败"
                }
            
            lines = result.stdout.strip().split("\n")
            
            if not lines or lines == [""]:
                return {
                    "success": True,
                    "output": "📭 暂无容器",
                    "containers": []
                }
            
            output_lines = ["# 🐳 容器状态", ""]
            output_lines.append("| 容器名 | 状态 | 端口 |")
            output_lines.append("|--------|------|------|")
            
            containers = []
            for line in lines:
                if not line:
                    continue
                parts = line.split("|")
                if len(parts) >= 2:
                    name = parts[0]
                    status = parts[1]
                    ports = parts[2] if len(parts) > 2 and parts[2] else "-"
                    
                    # 标记 HeiMaClaw 容器
                    if name.startswith("heimaclaw-"):
                        output_lines.append(f"| {name} | {status} | {ports} |")
                        containers.append({
                            "name": name,
                            "status": status,
                            "ports": ports,
                        })
            
            return {
                "success": True,
                "output": "\n".join(output_lines),
                "containers": containers
            }
        
        elif action == "stats":
            # 获取资源统计
            result = subprocess.run(
                [
                    "docker", "stats", "--no-stream", "--format",
                    "{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}|{{.MemPerc}}"
                ],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode != 0:
                return {
                    "success": False,
                    "error": "获取资源统计失败"
                }
            
            lines = result.stdout.strip().split("\n")
            
            output_lines = ["# 📊 资源使用统计", ""]
            output_lines.append("| 容器名 | CPU | 内存 | 使用率 |")
            output_lines.append("|--------|-----|------|--------|")
            
            resources = []
            for line in lines:
                if not line:
                    continue
                parts = line.split("|")
                if len(parts) >= 4:
                    name, cpu, mem_usage, mem_perc = parts[0], parts[1], parts[2], parts[3]
                    
                    if name.startswith("heimaclaw-"):
                        output_lines.append(f"| {name} | {cpu} | {mem_usage} | {mem_perc} |")
                        resources.append({
                            "name": name,
                            "cpu": cpu,
                            "memory_usage": mem_usage,
                            "memory_perc": mem_perc,
                        })
            
            # 如果 HeiMaClaw 没有容器，显示所有容器
            if not resources:
                return {
                    "success": True,
                    "output": "📭 暂无 HeiMaClaw 容器\n\n所有容器:\n" + result.stdout,
                    "resources": []
                }
            
            return {
                "success": True,
                "output": "\n".join(output_lines),
                "resources": resources
            }
        
        elif action == "inspect":
            # 查看单个容器详情
            if not project_name:
                return {
                    "success": False,
                    "error": "需要指定 project_name"
                }
            
            container_name = f"heimaclaw-{project_name}"
            
            result = subprocess.run(
                [
                    "docker", "inspect", container_name,
                    "--format", "{{json .}}"
                ],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode != 0:
                return {
                    "success": False,
                    "error": f"容器不存在: {container_name}"
                }
            
            try:
                info = json.loads(result.stdout)
                
                # 提取关键信息
                state = info.get("State", {})
                config = info.get("Config", {})
                host_config = info.get("HostConfig", {})
                
                output = f"""# 🔍 容器详情: {project_name}

**状态**: {state.get('Status', 'unknown')}
**运行中**: {state.get('Running', False)}
**重启次数**: {state.get('RestartCount', 0)}
**镜像**: {config.get('Image', '-')}

**资源限制**:
- 内存限制: {host_config.get('Memory', 0) / (1024*1024):.0f} MB
- CPU 配额: {host_config.get('CpuPeriod', 100000)} / {host_config.get('CpuQuota', 0)}

**创建时间**: {info.get('Created', '-')[:19]}"""
                
                return {
                    "success": True,
                    "output": output,
                    "details": {
                        "name": project_name,
                        "status": state.get('Status'),
                        "running": state.get('Running'),
                        "image": config.get('Image'),
                        "memory_limit_mb": host_config.get('Memory', 0) / (1024*1024),
                    }
                }
            
            except json.JSONDecodeError:
                return {
                    "success": False,
                    "error": "解析容器信息失败"
                }
        
        elif action == "alert":
            # 资源告警检查
            result = subprocess.run(
                [
                    "docker", "stats", "--no-stream", "--format",
                    "{{.Name}}|{{.CPUPerc}}|{{.MemPerc}}"
                ],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode != 0:
                return {"success": True, "alerts": []}
            
            alerts = []
            lines = result.stdout.strip().split("\n")
            
            for line in lines:
                if not line:
                    continue
                parts = line.split("|")
                if len(parts) >= 3:
                    name, cpu_str, mem_str = parts[0], parts[1].rstrip('%'), parts[2].rstrip('%')
                    
                    if not name.startswith("heimaclaw-"):
                        continue
                    
                    try:
                        cpu = float(cpu_str)
                        mem = float(mem_str)
                        
                        if cpu > 90:
                            alerts.append({
                                "type": "cpu",
                                "container": name,
                                "value": cpu,
                                "threshold": 90,
                                "message": f"⚠️ {name} CPU 使用率 {cpu}% 超过 90%"
                            })
                        
                        if mem > 90:
                            alerts.append({
                                "type": "memory",
                                "container": name,
                                "value": mem,
                                "threshold": 90,
                                "message": f"🚨 {name} 内存使用率 {mem}% 超过 90%"
                            })
                    
                    except ValueError:
                        continue
            
            if alerts:
                alert_lines = ["# 🚨 资源告警", ""]
                for a in alerts:
                    alert_lines.append(f"- {a['message']}")
                
                return {
                    "success": True,
                    "output": "\n".join(alert_lines),
                    "alerts": alerts,
                    "has_alerts": True
                }
            else:
                return {
                    "success": True,
                    "output": "✅ 所有容器资源使用正常",
                    "alerts": [],
                    "has_alerts": False
                }
        
        else:
            return {
                "success": False,
                "error": f"未知操作: {action}"
            }
    
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "监控命令执行超时"
        }
    except Exception as e:
        error(f"[docker_monitor] 错误: {e}")
        return {
            "success": False,
            "error": str(e)
        }


__all__ = ["MONITOR_TOOL_DEFINITION", "monitor_handler"]
