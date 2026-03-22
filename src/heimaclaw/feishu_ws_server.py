"""
飞书 WebSocket 长连接服务

独立的飞书长连接服务，支持 1 Agent = 1 Bot。
"""

import asyncio
import json
from typing import Optional

from heimaclaw.agent.router import AgentRouter
from heimaclaw.agent.runner import AgentRunner
from heimaclaw.agent.session import SessionManager
from heimaclaw.channel.base import InboundMessage
from heimaclaw.channel.feishu_ws import FeishuWebSocketAdapter
from heimaclaw.config.loader import get_config
from heimaclaw.console import error, info
from heimaclaw.interfaces import AgentConfig, ChannelType

# 全局状态
_agents: dict[str, AgentRunner] = {}
_session_managers: dict[str, SessionManager] = {}
_router: Optional[AgentRouter] = None

# app_id -> adapter 映射（避免同一个 app_id 创建多个 adapter）
_app_id_to_adapter: dict[str, FeishuWebSocketAdapter] = {}
# agent_name -> app_id 映射
_agent_to_app_id: dict[str, str] = {}


async def load_agents(default_feishu_config: dict) -> None:
    """加载所有 Agent 配置并初始化其对应的飞书 Adapter"""
    from pathlib import Path

    agents_dir = Path.home() / ".heimaclaw" / "agents"
    if not agents_dir.exists():
        agents_dir = Path("/opt/heimaclaw/data/agents")
        if not agents_dir.exists():
            info("暂无 Agent 配置")
            return

    for agent_dir in agents_dir.iterdir():
        if not agent_dir.is_dir():
            continue

        config_file = agent_dir / "agent.json"
        if not config_file.exists():
            continue

        try:
            with open(config_file, encoding="utf-8") as f:
                agent_data = json.load(f)

            if not agent_data.get("enabled", True):
                continue

            agent_name = agent_data.get("name", agent_dir.name)

            # 1. 创建会话管理器
            session_manager = SessionManager(
                data_dir=f"/tmp/heimaclaw/sessions/{agent_name}"
            )
            _session_managers[agent_name] = session_manager

            # 2. 创建 Agent Runner
            runner = AgentRunner(
                agent_id=agent_name,
                config=AgentConfig(
                    name=agent_name,
                    description=agent_data.get("description", ""),
                    channel=ChannelType.FEISHU,
                    model_provider=agent_data.get("llm", {}).get("provider", "zhipu"),
                    model_name=agent_data.get("llm", {}).get("model_name", "glm-4"),
                    sandbox_enabled=agent_data.get("sandbox", {}).get("enabled", False),
                ),
                session_manager=session_manager,
                llm_config=agent_data.get("llm", {}),
            )
            _agents[agent_name] = runner

            # 3. 处理独立飞书配置
            feishu_cfg = agent_data.get("feishu", {})
            app_id = feishu_cfg.get("app_id")
            app_secret = feishu_cfg.get("app_secret")

            if not app_id or not app_secret:
                app_id = default_feishu_config.get("app_id")
                app_secret = default_feishu_config.get("app_secret")

            if app_id and app_secret:
                _agent_to_app_id[agent_name] = app_id
                if app_id not in _app_id_to_adapter:
                    adapter = FeishuWebSocketAdapter({
                        "app_id": app_id,
                        "app_secret": app_secret
                    })
                    _app_id_to_adapter[app_id] = adapter
            
            info(f"加载 Agent: {agent_name} (App ID: {app_id})")

        except Exception as e:
            error(f"加载 Agent {agent_dir.name} 失败: {e}")


async def start_agents() -> None:
    """启动所有 Agent"""
    for agent_name, runner in _agents.items():
        try:
            await runner.start()
        except Exception as e:
            error(f"启动 Agent {agent_name} 失败: {e}")


async def stop_agents() -> None:
    """停止所有 Agent"""
    for agent_name, runner in _agents.items():
        try:
            await runner.stop()
        except Exception as e:
            error(f"停止 Agent {agent_name} 失败: {e}")



async def reload_agents() -> None:
    """重新加载所有 Agent 并重启服务"""
    info("检测到配置更新，正在热重载 Agent 设定...")
    # 停止当前 Agent
    await stop_agents()
    
    # 清空旧数据
    _agents.clear()
    _agent_to_app_id.clear()
    
    config = get_config()
    default_feishu_config = {}
    if hasattr(config, "channels") and hasattr(config.channels, "feishu"):
        feishu = config.channels.feishu
        if hasattr(feishu, "accounts") and feishu.accounts:
            default_account = feishu.get_default_account()
            if default_account:
                default_feishu_config = {
                    "app_id": default_account.app_id,
                    "app_secret": default_account.app_secret,
                }
        elif hasattr(feishu, "app_id"):
            default_feishu_config = {
                "app_id": feishu.app_id,
                "app_secret": feishu.app_secret,
            }
            
    # 重新加载
    await load_agents(default_feishu_config)
    await start_agents()
    info(f"Agent 热重载完成，当前在线 {len(_agents)} 个")

def _on_config_changed_hook(path):
    """配合 config loader 的钩子"""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(reload_agents())
    except Exception as e:
        error(f"热重载触发异常: {e}")

def create_message_handler(app_id: str):
    """闭包：为每个 Adapter 创建绑定的消息处理器"""
    
    async def handler(message: InboundMessage) -> None:
        global _router
        adapter = _app_id_to_adapter.get(app_id)
        if not adapter:
            return

        try:
            user_id = message.user_id
            chat_id = message.chat_id
            content = message.content

            # 判断是否群聊
            is_group = message.chat_type == "group"

            # 解析 @提及
            mentions = _router.parse_mentions(content)
            
            is_mentioned = False
            if mentions:
                for m in mentions:
                    m_lower = m.lower()
                    # 是否被 @
                    if m_lower in ["bot", "heimaclaw", "default", "ai"]:
                        is_mentioned = True
                        break
                    # 检查是否是飞书占位符格式
                    if m.startswith("_user_"):
                        is_mentioned = True
                        break
                    
                    # 检查是否@了某个属于该app_id的agent
                    for ag_name, ag_app in _agent_to_app_id.items():
                        if ag_app == app_id and m_lower == ag_name.lower():
                            is_mentioned = True
                            break
            
            # 内容预处理：移除飞书 @ 占位符
            import re
            content_clean = re.sub(r'<@_user_\d+>', '', content).strip()

            info(
                f"[{app_id[:6]}] 收到消息: user={user_id}, chat={chat_id}, "
                f"group={is_group}, is_mentioned={is_mentioned}, "
                f"mentions={mentions}, content={content[:80]}"
            )

            # 群聊不 @Bot → 发送确认消息后忽略
            if is_group and not is_mentioned:
                from heimaclaw.channel.base import OutboundMessage
                from heimaclaw.feishu.formatter import format_feishu_card

                ack_text = "💬 收到消息，请在消息前 @ 我以唤醒助手"
                ack_card = format_feishu_card(ack_text, agent_name="Bot")
                ack_outbound = OutboundMessage(
                    chat_id=chat_id,
                    content=ack_card,
                    message_type="interactive",
                )
                await adapter.send_message(ack_outbound)
                info("群聊未 @Bot，已发送提示消息")
                return

            # 确定 Agent 名称（只在属于当前 app_id 的 agent 中路由）
            # 简化路由逻辑：如果这个 app_id 只绑定了一个 agent，就直接用它
            valid_agents = [ag for ag, ap in _agent_to_app_id.items() if ap == app_id]
            
            if not valid_agents:
                error(f"没有找到绑定 App ID {app_id} 的 Agent")
                return

            agent_name = valid_agents[0]
            
            if is_group and is_mentioned:
                # 尝试通过 mention 路由
                routed_names = _router.route_with_mentions(
                    content=content, user_id=user_id, chat_id=chat_id, is_group=True
                )
                if routed_names and routed_names[0] in valid_agents:
                    agent_name = routed_names[0]

            runner = _agents.get(agent_name)
            if not runner:
                error(f"Agent 不存在: {agent_name}")
                return

            info(f"开始处理消息: agent={agent_name}, user={user_id}")

            # Typing Indicator
            typing_reaction_id = None
            if message.message_id:
                try:
                    typing_reaction_id = await adapter.add_typing_indicator(message.message_id)
                except Exception:
                    pass

            session_id = user_id if not is_group else None

            # 处理多模态（图片/文件/视频）下载
            content_obj = message.raw_data.get("content_obj", {})
            
            # 兼容飞书的 file_key, image_key, media_key
            if any(k in content_obj for k in ["image_key", "file_key", "media_key"]):
                if "image_key" in content_obj:
                    resource_type = "image"
                    resource_key = content_obj["image_key"]
                else:
                    resource_type = "file"
                    resource_key = content_obj.get("file_key") or content_obj.get("media_key")
                
                # 构建下载路径 /tmp/heimaclaw/agents/<name>/downloads/<key>
                import os
                download_dir = f"/tmp/heimaclaw/agents/{agent_name}/downloads"
                os.makedirs(download_dir, exist_ok=True)
                # 简单粗暴以 key 命名
                save_path = os.path.join(download_dir, resource_key)
                
                # 触发下载
                success = await adapter.download_resource(message.message_id, resource_key, resource_type, save_path)
                if success:
                    # 补充给 LLM
                    content_clean += f"\n[用户发送了一个{resource_type}，已保存在本地路径: {save_path}，你可以使用工具读取它]"
                else:
                    content_clean += f"\n[用户发送了一个{resource_type}，但系统下载失败]"

            # 处理消息
            response_text = await runner.process_message(
                user_id=user_id,
                channel=ChannelType.FEISHU,
                is_group=is_group,
                content=content_clean,
                session_id=session_id,
            )

            if hasattr(response_text, 'content'):
                response_text = getattr(response_text, 'content', str(response_text))
            elif not isinstance(response_text, str):
                response_text = str(response_text)

            # 发送回复
            from heimaclaw.channel.base import OutboundMessage
            from heimaclaw.feishu.formatter import format_feishu_card

            card_content = format_feishu_card(response_text, agent_name=agent_name)
            outbound = OutboundMessage(
                chat_id=chat_id if is_group else user_id,
                content=card_content,
                message_type="interactive",
            )

            if message.message_id and typing_reaction_id:
                try:
                    await adapter.remove_typing_indicator(message.message_id, typing_reaction_id)
                except Exception:
                    pass

            success = await adapter.send_message(outbound)
            if success:
                info(f"消息回复成功: {response_text[:50]}")
            else:
                error("消息回复失败")

        except Exception as e:
            msg_id = message.message_id if hasattr(message, "message_id") else "unknown"
            error(f"处理飞书消息失败: {e}, msg_id={msg_id}")
            import traceback
            traceback.print_exc()

    return handler


async def main() -> None:
    """主函数"""
    global _router

    info("HeiMaClaw 飞书多 Agent 长连接服务启动中...")
    _router = AgentRouter()
    config = get_config()

    default_feishu_config = {}
    if hasattr(config, "channels") and hasattr(config.channels, "feishu"):
        feishu = config.channels.feishu
        if hasattr(feishu, "accounts") and feishu.accounts:
            default_account = feishu.get_default_account()
            if default_account:
                default_feishu_config = {
                    "app_id": default_account.app_id,
                    "app_secret": default_account.app_secret,
                }
        elif hasattr(feishu, "app_id"):
            default_feishu_config = {
                "app_id": feishu.app_id,
                "app_secret": feishu.app_secret,
            }

    # 加载 Agent 并初始化对应的 Adapter
    await load_agents(default_feishu_config)

    if not _agents:
        error("没有可用的 Agent，请先创建 Agent: heimaclaw agent create <name>")
        return
        
    if not _app_id_to_adapter:
        error("没有任何有效的飞书 App ID 配置。请在 global 或 agent.json 中配置。")
        return

    
    # 启动配置热重载
    from heimaclaw.config.loader import start_config_watcher
    from heimaclaw.config.watcher import get_watcher
    start_config_watcher()
    
    # 注入业务层的重载钩子
    watcher = get_watcher()
    # 保存原始的 _on_config_file_changed (它负责清空 _config 缓存)
    original_callback = watcher.callback
    
    def wrapped_callback(path):
        if original_callback:
            original_callback(path)
        _on_config_changed_hook(path)
        
    watcher.set_callback(wrapped_callback)
    
# 启动 Agent
    await start_agents()

    info(f"服务已就绪: {len(_agents)} 个 Agent，{len(_app_id_to_adapter)} 个飞书连接")

    try:
        # 启动所有 Adapter 的长连接
        start_tasks = []
        for app_id, adapter in _app_id_to_adapter.items():
            handler = create_message_handler(app_id)
            start_tasks.append(adapter.start_listening(handler))
            
        await asyncio.gather(*start_tasks)
        
    except KeyboardInterrupt:
        info("收到停止信号...")
    finally:
        await stop_agents()
        for adapter in _app_id_to_adapter.values():
            await adapter.close()
        info("HeiMaClaw 服务已停止")


if __name__ == "__main__":
    asyncio.run(main())
