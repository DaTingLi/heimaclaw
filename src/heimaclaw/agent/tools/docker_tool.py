"""
Docker 项目管理工具

提供 Docker 容器化项目的查询和管理功能。
"""

from typing import Any

from heimaclaw.console import info, error

# 工具定义
DOCKER_TOOL_DEFINITION = {
    "name": "docker_project",
    "description": "Docker 项目管理工具 - 列出、查看、部署、启动、停止、删除 Docker 容器化项目",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "操作类型: list_projects, get_project, start, stop, delete, recover, logs, stats",
                "enum": ["list_projects", "get_project", "start", "stop", "delete", "recover", "logs", "stats", "deploy"]
            },
            "project_name": {
                "type": "string",
                "description": "项目名称"
            },
            "lines": {
                "type": "integer",
                "description": "日志行数（用于 logs 操作）",
                "default": 50
            },
            "force": {
                "type": "boolean",
                "description": "是否强制删除（跳过冷静期）",
                "default": False
            },
            "port": {
                "type": "integer",
                "description": "指定的宿主机端口（可选，不指定则自动分配）"
            }
        },
        "required": ["action"]
    }
}


def docker_project_handler(args: dict) -> dict:
    """
    Docker 项目管理工具处理器
    """
    import asyncio
    from heimaclaw.core.dockerimpl import get_project_manager, get_container_pool
    from heimaclaw.sandbox.docker import DockerSandboxBackend
    
    action = args.get("action")
    project_name = args.get("project_name")
    lines = args.get("lines", 50)
    force = args.get("force", False)
    
    try:
        pm = get_project_manager()
        container_pool = get_container_pool()
        
        if action == "list_projects":
            # 列出所有项目
            projects = pm.list_projects()
            
            if not projects:
                return {
                    "success": True,
                    "output": "暂无项目",
                    "projects": []
                }
            
            lines_output = ["# Docker 项目列表", ""]
            lines_output.append(f"| 项目名 | 状态 | 框架 | 端口 | 最后访问 |")
            lines_output.append("|--------|------|------|------|----------|")
            
            for p in projects:
                frameworks = ",".join(p.frameworks or []) or "-"
                ports = ",".join([f"{k}→{v}" for k, v in (p.ports or {}).items()]) or "-"
                last_access = p.last_accessed[:10] if p.last_accessed else "-"
                
                lines_output.append(f"| {p.name} | {p.status} | {frameworks} | {ports} | {last_access} |")
            
            return {
                "success": True,
                "output": "\n".join(lines_output),
                "projects": [
                    {
                        "name": p.name,
                        "status": p.status,
                        "frameworks": p.frameworks,
                        "ports": p.ports,
                    }
                    for p in projects
                ]
            }
        
        elif action == "get_project":
            # 获取项目详情
            if not project_name:
                return {"success": False, "error": "需要指定 project_name"}
            
            project = pm.get_project(project_name)
            
            if not project:
                return {"success": False, "error": f"项目不存在: {project_name}"}
            
            return {
                "success": True,
                "output": f"""# 项目: {project.name}

**状态**: {project.status}
**创建时间**: {project.created_at}
**最后访问**: {project.last_accessed}

**容器信息**:
- Container ID: {project.container_id or '-'}
- 镜像: {project.image or '-'}
- 端口映射: {project.ports}

**框架**: {', '.join(project.frameworks) if project.frameworks else '-'}
""",
                "project": {
                    "name": project.name,
                    "status": project.status,
                    "created_at": project.created_at,
                    "last_accessed": project.last_accessed,
                    "container_id": project.container_id,
                    "image": project.image,
                    "ports": project.ports,
                    "frameworks": project.frameworks,
                }
            }
        
        elif action == "logs":
            # 获取容器日志
            if not project_name:
                return {"success": False, "error": "需要指定 project_name"}
            
            logs = pm.get_container_logs(project_name, lines=lines)
            
            return {
                "success": True,
                "output": f"# {project_name} 日志 (最近 {lines} 行)\n\n```\n{logs}\n```",
                "logs": logs
            }
        
        elif action == "stats":
            # 获取统计信息
            container_stats = container_pool.get_stats()
            port_stats = container_pool._port_pool.get_stats()
            
            return {
                "success": True,
                "output": f"""# Docker 统计

**容器池**:
- 运行中: {container_stats['total']} / {container_stats['max']}
- 空闲超时: {container_stats['idle_timeout_seconds']} 秒

**端口池**:
- 已分配: {port_stats['total_allocated']}
- 预留: {port_stats['total_reserved']}
- 可用: {port_stats['available']}
- 范围: {port_stats['range']}
""",
                "stats": {
                    "containers": container_stats,
                    "ports": port_stats,
                }
            }
        
        elif action in ("start", "stop", "delete", "recover", "deploy"):
            # 需要异步操作
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                if action == "start":
                    loop.run_until_complete(pm.start_project(project_name))
                    return {"success": True, "output": f"项目已启动: {project_name}"}
                
                elif action == "stop":
                    loop.run_until_complete(pm.stop_project(project_name))
                    return {"success": True, "output": f"项目已停止: {project_name}"}
                
                elif action == "delete":
                    result = pm.delete_project(project_name, force=force)
                    return {"success": result["success"], "output": result["message"]}
                
                elif action == "recover":
                    success = loop.run_until_complete(pm.recover_project(project_name))
                    if success:
                        return {"success": True, "output": f"项目已恢复: {project_name}"}
                    else:
                        return {"success": False, "output": f"项目恢复失败: {project_name}"}
                
                elif action == "deploy":
                    # 部署项目（支持指定端口）
                    preferred_port = args.get("port")
                    
                    # 获取或创建容器
                    async def _deploy():
                        container = await container_pool.get_container(project_name, preferred_port=preferred_port)
                        await container.ensure()
                        return container
                    
                    container = loop.run_until_complete(_deploy())
                    
                    # 获取端口映射
                    ports_info = []
                    for cp, hp in container.host_ports.items():
                        ports_info.append(f"{hp}→{cp}")
                    ports_str = ", ".join(ports_info) if ports_info else "-"
                    
                    output = f"""项目 {project_name} 部署成功！

**端口映射**: {ports_str}

**访问地址**: http://<宿主机IP>:{container.host_ports.get(5000, 'N/A')}/

**状态**: {container.status.value if hasattr(container.status, 'value') else container.status}"""
                    
                    return {"success": True, "output": output, "ports": container.host_ports}
            
            finally:
                loop.close()
        
        else:
            return {"success": False, "error": f"未知操作: {action}"}
    
    except Exception as e:
        error(f"[docker_project] 错误: {e}")
        return {"success": False, "error": str(e)}


__all__ = ["DOCKER_TOOL_DEFINITION", "docker_project_handler"]
