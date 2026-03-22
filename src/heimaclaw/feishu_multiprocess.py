"""
飞书 WebSocket 长连接服务 - 多进程架构

每个飞书 App 在独立进程中运行，避免 event loop 冲突。
工业级方案：支持多 Agent + 多飞书 App 真正并行。
"""

import asyncio
import json
import multiprocessing as mp
import os
import signal
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

# 设置启动方法为 spawn（避免 fork 问题）
try:
    mp.set_start_method('spawn', force=True)
except RuntimeError:
    pass  # 已设置

from heimaclaw.agent.router import AgentRouter
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
    app_id: str
    app_secret: str
    llm_config: dict
    sandbox_enabled: bool
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
        # 创建 Agent
        session_manager = SessionManager(
            data_dir=f"/tmp/heimaclaw/sessions/{self.agent_info.name}"
        )

        # 创建 Agent Runner
        from heimaclaw.interfaces import AgentConfig, ChannelType
        
        runner = AgentRunner(
            agent_id=self.agent_info.name,
            config=AgentConfig(
                name=self.agent_info.name,
                description=f"{self.agent_info.name} Agent",
                channel=ChannelType.FEISHU,
                model_provider=self.agent_info.llm_config.get("provider", "zhipu"),
                model_name=self.agent_info.llm_config.get("model_name", "glm-4"),
                sandbox_enabled=self.agent_info.sandbox_enabled,
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

        # 创建消息处理器
        async def message_handler(message: InboundMessage) -> None:
            try:
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
                
                # 处理消息
                response = await runner.process_message(
                    user_id=message.user_id,
                    channel=ChannelType.FEISHU,
                    content=message.content,
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
            agents_dir = Path("/opt/heimaclaw/data/agents")
        
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

                agent_info = AgentInfo(
                    name=agent_name,
                    app_id=app_id,
                    app_secret=app_secret,
                    llm_config=data.get("llm", {}),
                    sandbox_enabled=data.get("sandbox", {}).get("enabled", False),
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
