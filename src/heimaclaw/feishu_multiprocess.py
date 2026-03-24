"""
飞书 WebSocket 长连接服务 - 多进程架构

每个飞书 App 在独立进程中运行，避免 event loop 冲突。
工业级方案：支持多 Agent + 多飞书 App 真正并行。
"""

import heimaclaw.paths as paths
import asyncio
import json
import multiprocessing as mp
import os
import signal
import sys
import threading
import time
from dataclasses import dataclass
import base64
from pathlib import Path
from typing import Any, Optional
import asyncio

# 设置启动方法为 spawn（避免 fork 问题）
try:
    mp.set_start_method('spawn', force=True)
except RuntimeError:
    pass  # 已设置

from heimaclaw.agent.router import AgentRouter
from heimaclaw.interfaces import AgentConfig, ChannelType, SandboxBackend
from heimaclaw.agent.runner import AgentRunner
from heimaclaw.agent.session import SessionManager
from heimaclaw.channel.base import InboundMessage
from heimaclaw.channel.feishu_ws import FeishuWebSocketAdapter
from heimaclaw.config.loader import get_config
from heimaclaw.console import error, info, warning


@dataclass
class AgentInfo:
    """Agent 信息"""
    name: str
    display_name: str  # 对外展示的名称（飞书显示名）
    app_id: str
    app_secret: str
    llm_config: dict
    sandbox_enabled: bool
    sandbox_type: str  # "firecracker", "docker", "process"
    workspace: str


class FeishuWorker(mp.Process):
    """
    飞书 Worker 进程
    
    每个进程独立运行一个 Feishu App + Agent Runner
    """

    def __init__(self, agent_info: AgentInfo):
        super().__init__(daemon=True)
        self.agent_info = agent_info
        self._running = mp.Value('i', 0)

    def run(self) -> None:
        """在独立进程中运行"""
        import asyncio
        
        info(f"[Worker {self.agent_info.name}] 启动，App ID: {self.agent_info.app_id[:10]}...")

        # 创建独立的 event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._running.value = 1

        try:
            loop.run_until_complete(self._run())
        except KeyboardInterrupt:
            info(f"[Worker {self.agent_info.name}] 被中断")
        except Exception as e:
            error(f"[Worker {self.agent_info.name}] 运行异常: {e}")
        finally:
            self._running.value = 0
            loop.close()
            info(f"[Worker {self.agent_info.name}] 已停止")

    async def _run(self) -> None:
        """异步主循环"""
        # 初始化全局视觉服务（优先全局配置，Agent 可覆盖）
        from heimaclaw.vision import get_vision_service, VisionConfig
        from heimaclaw.config.loader import get_config
        from heimaclaw.agent.tools.feishu_doc_tool import set_feishu_credentials
        
        config = get_config()
        vision_cfg = getattr(config, 'vision', None) or VisionConfig()
        
        # Agent 级别的 vision 配置可以覆盖全局（如果 agent.json 中有 vision 字段）
        agent_vision = self.agent_info.llm_config.get("vision", {})
        if agent_vision:
            vision_cfg.enabled = agent_vision.get("enabled", vision_cfg.enabled)
            vision_cfg.model = agent_vision.get("model", vision_cfg.model)
            vision_cfg.api_key = agent_vision.get("api_key", vision_cfg.api_key)
            vision_cfg.base_url = agent_vision.get("base_url", vision_cfg.base_url)
        
        if vision_cfg.enabled and vision_cfg.api_key:
            get_vision_service().configure(VisionConfig(
                enabled=True,
                model=vision_cfg.model,
                api_key=vision_cfg.api_key,
                base_url=vision_cfg.base_url,
                timeout=getattr(vision_cfg, 'timeout', 60),
                max_retries=getattr(vision_cfg, 'max_retries', 3),
            ))
            info(f"[Worker {self.agent_info.name}] 全局视觉服务已启用，模型: {vision_cfg.model}")
        elif vision_cfg.enabled and not vision_cfg.api_key:
            warning(f"[Worker {self.agent_info.name}] 视觉服务已启用但未配置 API Key")
        
        # 创建 Agent
        session_manager = SessionManager(
            data_dir=f"/tmp/heimaclaw/sessions/{self.agent_info.name}"
        )

        # 设置飞书凭证（供 feishu_doc_tool 使用）
        set_feishu_credentials(self.agent_info.app_id, self.agent_info.app_secret)

        # 创建 Agent Runner
        
        runner = AgentRunner(
            agent_id=self.agent_info.name,
            config=AgentConfig(
                name=self.agent_info.name,
                description=f"{self.agent_info.name} Agent",
                channel=ChannelType.FEISHU,
                model_provider=self.agent_info.llm_config.get("provider", "zhipu"),
                model_name=self.agent_info.llm_config.get("model_name", "glm-4"),
                sandbox_enabled=self.agent_info.sandbox_enabled,
                sandbox_backend_type=SandboxBackend(getattr(self.agent_info, 'sandbox_type', "docker")),
            ),
            session_manager=session_manager,
            llm_config=self.agent_info.llm_config,
        )

        # 启动 Agent
        await runner.start()
        info(f"[Worker {self.agent_info.name}] Agent 已启动")

        # 创建飞书适配器
        adapter = FeishuWebSocketAdapter({
            "app_id": self.agent_info.app_id,
            "app_secret": self.agent_info.app_secret,
        })
        self._ws_adapter = adapter  # 保存引用用于下载图片

        # 创建消息处理器
        async def message_handler(message: InboundMessage) -> None:
            try:
                # 【关键】处理图片（如果消息包含图片）
                content = message.content
                image_keys = getattr(message, 'image_keys', [])
                image_urls = getattr(message, 'image_urls', [])
                
                if image_keys or image_urls:
                    vision_service = get_vision_service()
                    if vision_service.is_enabled():
                        try:
                            image_descriptions = []
                            
                            # 处理飞书 image_keys（需要下载）
                            for img_key in image_keys:
                                try:
                                    # 下载图片
                                    import tempfile
                                    import os
                                    from pathlib import Path
                                    
                                    # 使用 adapter 下载（如果可用）
                                    if hasattr(self, '_ws_adapter') and self._ws_adapter:
                                        tmp_path = f"/tmp/vision_{img_key}.jpg"
                                        success = await self._ws_adapter.download_resource(
                                            message_id=message.message_id,
                                            file_key=img_key,
                                            resource_type="image",
                                            save_path=tmp_path
                                        )
                                        if success and os.path.exists(tmp_path):
                                            with open(tmp_path, 'rb') as f:
                                                img_b64 = base64.b64encode(f.read()).decode()
                                            desc = await vision_service.understand_image(
                                                image_data=img_b64,
                                                prompt="请描述这张图片的内容",
                                                agent_id=self.agent_info.name
                                            )
                                            info(f"[DEBUG] Vision 返回描述: '{desc}' (长度={len(desc) if desc else 0})")
                                            if desc and desc.strip():
                                                image_descriptions.append(f"[图片描述: {desc.strip()}]")
                                            else:
                                                image_descriptions.append("[图片无法识别]")
                                            os.remove(tmp_path)
                                        else:
                                            image_descriptions.append("[图片下载失败]")
                                except Exception as e:
                                    warning(f"[Worker {self.agent_info.name}] 下载图片失败: {e}")
                                    image_descriptions.append(f"[图片处理失败: {str(e)[:50]}]")
                            
                            # 处理外部 image_urls
                            for img_url in image_urls:
                                try:
                                    desc = await vision_service.understand_image(
                                        image_data=img_url,
                                        prompt="请描述这张图片的内容",
                                        agent_id=self.agent_info.name
                                    )
                                    image_descriptions.append(f"[图片描述: {desc}]")
                                except Exception as e:
                                    image_descriptions.append(f"[图片理解失败: {str(e)[:50]}]")
                            
                            if image_descriptions:
                                info(f"[DEBUG] Vision image_descriptions: {image_descriptions}")
                                content = "\n".join(image_descriptions) + "\n" + content
                                info(f"[Worker {self.agent_info.name}] 已理解 {len(image_descriptions)} 张图片")
                        except Exception as e:
                            warning(f"[Worker {self.agent_info.name}] 视觉理解失败: {e}")
                
                # 【关键】群聊时检查是否 @mentioned 当前机器人
                # 使用双向模糊匹配，自动适配不同命名的机器人
                if message.chat_type == "group":
                    bot_mentioned = False
                    display_lower = self.agent_info.display_name.lower()
                    
                    # 方法1: 检查 mentions 列表（飞书 SDK 提供的被 @ 名称列表）
                    if message.mentions:
                        for mention in message.mentions:
                            mention_lower = mention.lower()
                            # 双向包含检查：display_name in mention OR mention in display_name
                            if display_lower in mention_lower or mention_lower in display_lower:
                                bot_mentioned = True
                                break
                    
                    # 方法2: 检查消息内容中的 @mention 模式
                    if not bot_mentioned:
                        import re
                        content_lower = message.content.lower()
                        # 匹配 @后面跟字母数字下划线的模式
                        mentions_found = re.findall(r'@([a-z0-9_]+)', content_lower)
                        for mentioned_name in mentions_found:
                            if display_lower in mentioned_name or mentioned_name in display_lower:
                                bot_mentioned = True
                                break
                    
                    if not bot_mentioned:
                        # 群聊但没有被 @，跳过处理
                        return
                
                # 添加 Typing Indicator
                typing_id = None
                if message.message_id:
                    try:
                        typing_id = await adapter.add_typing_indicator(message.message_id)
                    except Exception:
                        pass
                
                # 使用 user_id + app_id 的组合作为 session_id
                # 因为同一个用户可能使用多个飞书机器人 App
                session_id = f"{message.user_id}_{self.agent_info.app_id}"
                
                # 处理消息（使用经过视觉处理的 content，不是原始 message.content）
                response = await runner.process_message(
                    user_id=message.user_id,
                    channel=ChannelType.FEISHU,
                    content=content,
                    session_id=session_id,
                )
                
                # 移除 Typing Indicator
                if typing_id:
                    try:
                        await adapter.remove_typing_indicator(typing_id)
                    except Exception:
                        pass
                
                # 发送响应
                if response:
                    from heimaclaw.channel.base import OutboundMessage
                    outbound = OutboundMessage(
                        chat_id=message.chat_id,
                        content=response,
                    )
                    await adapter.send_message(outbound)
            except Exception as e:
                error(f"[Worker {self.agent_info.name}] 消息处理异常: {e}")

        # 启动飞书 WebSocket
        await adapter.start_listening(message_handler)
        info(f"[Worker {self.agent_info.name}] 飞书 WebSocket 已连接")

        # 保持运行
        while self._running.value == 1:
            await asyncio.sleep(1)

        # 停止
        await adapter.stop()
        await runner.stop()


class MultiProcessFeishuService:
    """
    多进程飞书服务
    
    管理多个 Worker 进程，每个进程运行一个飞书 App + Agent
    """

    def __init__(self):
        self.workers: dict[str, FeishuWorker] = {}
        self._manager = None
        self._shared_state = None

    def _init_manager(self):
        """延迟初始化 Manager"""
        if self._manager is None:
            self._manager = mp.Manager()
            self._shared_state = self._manager.dict()

    def _load_agent_configs(self) -> list[AgentInfo]:
        """加载所有 Agent 配置"""
        agents = []
        
        # 优先从 ~/.heimaclaw/agents/ 加载
        agents_dir = Path.home() / ".heimaclaw" / "agents"
        if not agents_dir.exists():
            agents_dir = paths.AGENTS_DIR
        
        if not agents_dir.exists():
            warning("未找到 Agent 配置目录")
            return agents

        # 加载全局飞书配置
        config = get_config()
        default_feishu = {}
        if hasattr(config, "channels") and hasattr(config.channels, "feishu"):
            feishu = config.channels.feishu
            if hasattr(feishu, "app_id") and feishu.app_id:
                default_feishu = {"app_id": feishu.app_id, "app_secret": feishu.app_secret}

        for agent_dir in agents_dir.iterdir():
            if not agent_dir.is_dir():
                continue
            
            config_file = agent_dir / "agent.json"
            if not config_file.exists():
                continue

            try:
                with open(config_file, encoding="utf-8") as f:
                    data = json.load(f)

                if not data.get("enabled", True):
                    continue

                agent_name = data.get("name", agent_dir.name)

                # 获取飞书配置
                feishu_cfg = data.get("feishu", {})
                app_id = feishu_cfg.get("app_id") or default_feishu.get("app_id")
                app_secret = feishu_cfg.get("app_secret") or default_feishu.get("app_secret")

                if not app_id or not app_secret:
                    warning(f"Agent {agent_name} 缺少飞书配置，跳过")
                    continue

                # 构建 llm_config，包含 display_name
                llm_cfg = data.get("llm", {})
                llm_cfg["display_name"] = data.get("display_name", agent_name)
                
                agent_info = AgentInfo(
                    name=agent_name,
                    display_name=data.get("display_name", agent_name),
                    app_id=app_id,
                    app_secret=app_secret,
                    llm_config=llm_cfg,
                    sandbox_enabled=data.get("sandbox", {}).get("enabled", True),
                    sandbox_type=data.get("sandbox", {}).get("type", "docker"),
                    workspace=str(agent_dir),
                )
                agents.append(agent_info)
                info(f"加载 Agent: {agent_name} (App: {app_id[:10]}...)")

            except Exception as e:
                error(f"加载 Agent {agent_dir.name} 失败: {e}")

        return agents

    def start(self) -> None:
        """启动所有 Worker"""
        agents = self._load_agent_configs()

        if not agents:
            warning("没有 Agent 需要启动")
            return

        info(f"准备启动 {len(agents)} 个 Worker 进程...")

        for agent_info in agents:
            # 检查是否已有相同 app_id 的 worker
            existing = [w for w in self.workers.values() 
                       if w.agent_info.app_id == agent_info.app_id]
            if existing:
                info(f"跳过 {agent_info.name}，App {agent_info.app_id[:10]}... 已存在 Worker")
                continue

            # 创建并启动 Worker
            worker = FeishuWorker(agent_info)
            worker.start()
            self.workers[agent_info.name] = worker
            info(f"Worker {agent_info.name} 已启动 (PID: {worker.pid})")

        info(f"服务已就绪，共 {len(self.workers)} 个 Worker 运行中")

    def stop(self) -> None:
        """停止所有 Worker"""
        info("正在停止所有 Worker...")
        
        for name, worker in self.workers.items():
            try:
                worker._running.value = 0
                worker.terminate()
                worker.join(timeout=5)
                if worker.is_alive():
                    worker.kill()
                info(f"Worker {name} 已停止")
            except Exception as e:
                error(f"停止 Worker {name} 失败: {e}")

        self.workers.clear()
        info("所有 Worker 已停止")

    def status(self) -> dict:
        """获取服务状态"""
        return {
            "workers": len(self.workers),
            "running": [name for name, w in self.workers.items() if w.is_alive()],
            "dead": [name for name, w in self.workers.items() if not w.is_alive()],
        }


# 全局实例
_service: Optional[MultiProcessFeishuService] = None


def start_service() -> MultiProcessFeishuService:
    """启动多进程服务"""
    global _service
    
    if _service is not None:
        warning("服务已在运行")
        return _service

    _service = MultiProcessFeishuService()
    _service.start()
    return _service


def stop_service() -> None:
    """停止服务"""
    global _service
    
    if _service is None:
        return
    
    _service.stop()
    _service = None


def get_service() -> Optional[MultiProcessFeishuService]:
    """获取服务实例"""
    return _service


async def main() -> None:
    """主入口"""
    service = start_service()
    
    # 等待中断信号
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        info("收到中断信号")
    finally:
        stop_service()


if __name__ == "__main__":
    asyncio.run(main())
