"""
Snapshot 快照工具

提供项目快照的创建、恢复、列表功能。
用户说话就能用：帮我保存快照、帮我恢复项目
"""

from typing import Any

from heimaclaw.console import info, error

# 工具定义
SNAPSHOT_TOOL_DEFINITION = {
    "name": "docker_snapshot",
    "description": """Docker 项目快照工具 - 保存和恢复项目代码快照

用途：
- 保存项目当前状态（防止代码丢失）
- 从快照恢复项目（回退到之前的状态）
- 列出项目快照历史

使用场景：
- 用户说"帮我保存快照" → 调用 snapshot_save
- 用户说"帮我恢复到之前的版本" → 调用 snapshot_restore
- 用户说"看看有哪些快照" → 调用 snapshot_list""",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "操作类型: save(保存快照), restore(恢复快照), list(列出快照), delete(删除快照)",
                "enum": ["save", "restore", "list", "delete"]
            },
            "project_name": {
                "type": "string",
                "description": "项目名称"
            },
            "description": {
                "type": "string",
                "description": "快照描述（如：'重构前的备份'）",
                "default": ""
            },
            "snapshot_id": {
                "type": "string",
                "description": "快照ID（用于恢复或删除）"
            },
            "force": {
                "type": "boolean",
                "description": "是否强制恢复（覆盖现有项目）",
                "default": False
            }
        },
        "required": ["action", "project_name"]
    }
}


def snapshot_handler(args: dict) -> dict:
    """
    快照工具处理器
    """
    from heimaclaw.core.dockerimpl import get_snapshot_manager
    
    action = args.get("action")
    project_name = args.get("project_name")
    description = args.get("description", "")
    snapshot_id = args.get("snapshot_id")
    force = args.get("force", False)
    
    try:
        snapshot_mgr = get_snapshot_manager()
        
        if action == "save":
            # 创建快照
            snapshot = snapshot_mgr.create_snapshot(
                project_name=project_name,
                description=description or f"手动快照",
            )
            
            size_mb = snapshot.size / (1024 * 1024)
            
            return {
                "success": True,
                "output": f"""✅ 快照已保存！

**项目**: {snapshot.project_name}
**快照ID**: {snapshot.snapshot_id}
**大小**: {size_mb:.2f} MB
**时间**: {snapshot.created_at}
**描述**: {snapshot.description}

可以使用 snapshot_restore 恢复到该版本。""",
                "snapshot_id": snapshot.snapshot_id,
                "size": snapshot.size,
            }
        
        elif action == "list":
            # 列出快照
            snapshots = snapshot_mgr.list_snapshots(project_name)
            
            if not snapshots:
                return {
                    "success": True,
                    "output": f"📭 项目 {project_name} 暂无快照",
                    "snapshots": []
                }
            
            lines = [f"# {project_name} 快照列表", ""]
            lines.append(f"| 快照ID | 时间 | 大小 | 描述 |")
            lines.append("|--------|------|------|------|")
            
            for s in snapshots:
                size_mb = s.size / (1024 * 1024)
                time_str = s.created_at[:19]
                desc = s.description or "-"
                lines.append(f"| {s.snapshot_id} | {time_str} | {size_mb:.1f}MB | {desc} |")
            
            return {
                "success": True,
                "output": "\n".join(lines),
                "snapshots": [
                    {
                        "id": s.snapshot_id,
                        "time": s.created_at,
                        "size": s.size,
                        "description": s.description,
                    }
                    for s in snapshots
                ]
            }
        
        elif action == "restore":
            # 恢复快照 - 需要找到快照路径
            if not snapshot_id:
                return {
                    "success": False,
                    "error": "需要指定 snapshot_id 来恢复快照"
                }
            
            # 查找快照
            snapshots = snapshot_mgr.list_snapshots(project_name)
            target = None
            for s in snapshots:
                if s.snapshot_id == snapshot_id:
                    target = s
                    break
            
            if not target:
                return {
                    "success": False,
                    "error": f"快照不存在: {snapshot_id}"
                }
            
            success = snapshot_mgr.restore_snapshot(
                project_name=project_name,
                snapshot_path=target.path,
                force=force,
            )
            
            if success:
                return {
                    "success": True,
                    "output": f"""✅ 项目已恢复到快照 {snapshot_id}

⚠️ 注意：恢复会覆盖当前代码，请确认是否正确。""",
                }
            else:
                return {
                    "success": False,
                    "error": f"恢复失败: {snapshot_id}"
                }
        
        elif action == "delete":
            # 删除快照 - 需要找到快照路径
            if not snapshot_id:
                return {
                    "success": False,
                    "error": "需要指定 snapshot_id 来删除快照"
                }
            
            # 查找快照
            snapshots = snapshot_mgr.list_snapshots(project_name)
            target = None
            for s in snapshots:
                if s.snapshot_id == snapshot_id:
                    target = s
                    break
            
            if not target:
                return {
                    "success": False,
                    "error": f"快照不存在: {snapshot_id}"
                }
            
            success = snapshot_mgr.delete_snapshot(snapshot_path=target.path)
            
            if success:
                return {
                    "success": True,
                    "output": f"🗑️ 快照已删除: {snapshot_id}"
                }
            else:
                return {
                    "success": False,
                    "error": f"删除失败: {snapshot_id}"
                }
        
        else:
            return {
                "success": False,
                "error": f"未知操作: {action}"
            }
    
    except FileNotFoundError as e:
        return {
            "success": False,
            "error": str(e)
        }
    except Exception as e:
        error(f"[docker_snapshot] 错误: {e}")
        return {
            "success": False,
            "error": str(e)
        }


__all__ = ["SNAPSHOT_TOOL_DEFINITION", "snapshot_handler"]
