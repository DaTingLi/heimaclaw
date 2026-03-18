"""
预热池模块

管理预热的 microVM 实例池，实现快速实例获取。
"""

import asyncio
import time

from heimaclaw.console import info, sandbox_event, warning
from heimaclaw.sandbox.base import InstanceInfo, SandboxBackend


class WarmPool:
    """
    预热池

    维护一组预热的 microVM 实例，实现快速获取。
    目标：预热后获取实例 < 50ms。
    """

    def __init__(
        self,
        backend: SandboxBackend,
        pool_size: int = 5,
        warm_on_init: bool = True,
    ):
        """
        初始化预热池

        参数:
            backend: 沙箱后端
            pool_size: 池大小
            warm_on_init: 是否在初始化时预热
        """
        self.backend = backend
        self.pool_size = pool_size
        self.warm_on_init = warm_on_init

        self._pool: list[InstanceInfo] = []
        self._lock = asyncio.Lock()
        self._warming = False

    async def initialize(self) -> None:
        """
        初始化预热池

        如果 warm_on_init 为 True，则预热实例。
        """
        if not self.warm_on_init:
            return

        await self.warm_up()

    async def warm_up(self) -> None:
        """
        预热实例

        创建预热的实例填充池。
        """
        async with self._lock:
            if self._warming:
                return

            self._warming = True

        try:
            needed = self.pool_size - len(self._pool)

            if needed <= 0:
                return

            sandbox_event(f"预热 {needed} 个 microVM 实例")

            # 并行创建实例
            tasks = []
            for _ in range(needed):
                task = asyncio.create_task(
                    self.backend.create_instance(
                        agent_id="__warm_pool__",
                        memory_mb=64,  # 预热实例使用较小内存
                        cpu_count=1,
                    )
                )
                tasks.append(task)

            instances = await asyncio.gather(*tasks, return_exceptions=True)

            for instance in instances:
                if isinstance(instance, Exception):
                    warning(f"预热实例失败: {instance}")
                    continue

                if isinstance(instance, InstanceInfo):
                    self._pool.append(instance)

            sandbox_event(f"预热完成，当前池大小: {len(self._pool)}")

        finally:
            self._warming = False

    async def claim(
        self,
        agent_id: str,
        timeout_ms: int = 5000,
    ) -> InstanceInfo:
        """
        获取一个实例

        优先从预热池获取，如果池为空则创建新实例。

        参数:
            agent_id: Agent ID
            timeout_ms: 超时时间（毫秒）

        返回:
            实例信息
        """
        start_time = time.time()

        async with self._lock:
            # 尝试从池中获取
            if self._pool:
                instance = self._pool.pop(0)

                # 更新 agent_id
                instance.agent_id = agent_id

                duration_ms = int((time.time() - start_time) * 1000)
                sandbox_event(
                    f"从预热池获取实例: {instance.instance_id} (耗时: {duration_ms}ms)"
                )

                # 异步补充池
                asyncio.create_task(self._refill())

                return instance

        # 池为空，创建新实例
        info("预热池为空，创建新实例")

        instance = await asyncio.wait_for(
            self.backend.create_instance(agent_id=agent_id),
            timeout=timeout_ms / 1000,
        )

        duration_ms = int((time.time() - start_time) * 1000)
        sandbox_event(f"创建新实例: {instance.instance_id} (耗时: {duration_ms}ms)")

        return instance

    async def release(self, instance: InstanceInfo) -> None:
        """
        释放实例回池

        如果池未满，将实例放回池中；否则销毁实例。

        参数:
            instance: 要释放的实例
        """
        async with self._lock:
            if len(self._pool) < self.pool_size:
                # 重置实例状态
                instance.agent_id = "__warm_pool__"
                self._pool.append(instance)
                sandbox_event(f"实例释放回池: {instance.instance_id}")
            else:
                # 池已满，销毁实例
                await self.backend.destroy_instance(instance.instance_id)
                sandbox_event(f"池已满，销毁实例: {instance.instance_id}")

    async def _refill(self) -> None:
        """
        补充池
        """
        needed = self.pool_size - len(self._pool)

        if needed <= 0:
            return

        try:
            instance = await self.backend.create_instance(
                agent_id="__warm_pool__",
                memory_mb=64,
                cpu_count=1,
            )

            async with self._lock:
                if len(self._pool) < self.pool_size:
                    self._pool.append(instance)

        except Exception as e:
            warning(f"补充预热池失败: {e}")

    async def drain(self) -> None:
        """
        清空池

        销毁池中所有实例。
        """
        async with self._lock:
            for instance in self._pool:
                try:
                    await self.backend.destroy_instance(instance.instance_id)
                except Exception as e:
                    warning(f"销毁实例 {instance.instance_id} 失败: {e}")

            self._pool.clear()
            sandbox_event("预热池已清空")

    @property
    def size(self) -> int:
        """当前池大小"""
        return len(self._pool)

    @property
    def capacity(self) -> int:
        """池容量"""
        return self.pool_size

    @property
    def available(self) -> int:
        """可用实例数"""
        return len(self._pool)
