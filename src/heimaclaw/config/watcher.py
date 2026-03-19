"""
配置文件监听器模块

使用 watchdog 监控配置文件变化，支持热重载。
"""

import threading
from pathlib import Path
from typing import Callable, List, Optional, Set

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from heimaclaw.console import error, info, warning


class ConfigFileHandler(FileSystemEventHandler):
    """配置文件事件处理器"""

    def __init__(self, extensions: Set[str], callback: Callable[[Path], None]):
        """
        初始化处理器

        参数:
            extensions: 要监听的文件扩展名（如 {".toml", ".yaml"}）
            callback: 文件变化时的回调函数，参数为变化的文件路径
        """
        self.extensions = extensions
        self.callback = callback
        self._debounce_timers: dict = {}
        self._debounce_seconds = 0.5  # 防抖延迟

    def on_modified(self, event: FileSystemEvent):
        """文件修改事件"""
        if event.is_directory:
            return

        path = Path(str(event.src_path))
        if path.suffix in self.extensions:
            self._debounced_callback(path)

    def on_created(self, event: FileSystemEvent):
        """文件创建事件"""
        if event.is_directory:
            return

        path = Path(str(event.src_path))
        if path.suffix in self.extensions:
            self._debounced_callback(path)

    def on_deleted(self, event: FileSystemEvent):
        """文件删除事件"""
        if event.is_directory:
            return

        path = Path(str(event.src_path))
        if path.suffix in self.extensions:
            info(f"配置文件已删除: {path}")

    def _debounced_callback(self, path: Path):
        """防抖回调"""
        import time

        timer_key = str(path)
        current_time = time.time()

        # 检查是否需要处理
        if timer_key in self._debounce_timers:
            last_time = self._debounce_timers[timer_key]
            if current_time - last_time < self._debounce_seconds:
                return

        self._debounce_timers[timer_key] = current_time
        info(f"检测到配置文件变化: {path}")
        self.callback(path)


class ConfigWatcher:
    """
    配置热重载监听器

    监控指定目录下的配置文件变化，触发回调。
    """

    def __init__(
        self,
        watch_paths: List[Path],
        extensions: Optional[Set[str]] = None,
        callback: Optional[Callable[[Path], None]] = None,
    ):
        """
        初始化监听器

        参数:
            watch_paths: 要监听的目标路径列表
            extensions: 要监听的文件扩展名，默认 {".toml", ".yaml", ".yml", ".json"}
            callback: 文件变化时的回调函数
        """
        self.watch_paths = [Path(p) for p in watch_paths]
        self.extensions = extensions or {".toml", ".yaml", ".yml", ".json", ".md"}
        self.callback = callback

        self._observer: Optional[Observer] = None
        self._handler: Optional[ConfigFileHandler] = None
        self._running = False
        self._lock = threading.Lock()

    def set_callback(self, callback: Callable[[Path], None]):
        """
        设置回调函数

        参数:
            callback: 文件变化时的回调函数
        """
        self.callback = callback

    def start(self):
        """
        启动监听（线程安全）
        """
        with self._lock:
            if self._running:
                warning("ConfigWatcher 已经启动")
                return

            if self.callback is None:
                error("未设置回调函数，无法启动 ConfigWatcher")
                return

            self._handler = ConfigFileHandler(self.extensions, self.callback)
            self._observer = Observer()

            for path in self.watch_paths:
                if not path.exists():
                    warning(f"监听路径不存在: {path}")
                    continue

                recursive = path.is_dir()
                self._observer.schedule(
                    self._handler,
                    str(path),
                    recursive=recursive,
                )
                info(f"开始监听: {path}" + (" (递归)" if recursive else ""))

            self._observer.start()
            self._running = True
            info("ConfigWatcher 已启动")

    def stop(self):
        """
        停止监听（线程安全）
        """
        with self._lock:
            if not self._running:
                return

            if self._observer:
                self._observer.stop()
                self._observer.join(timeout=5)
                self._observer = None

            self._running = False
            self._handler = None
            info("ConfigWatcher 已停止")

    def is_running(self) -> bool:
        """检查监听器是否运行中"""
        return self._running

    def __enter__(self):
        """上下文管理器入口"""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.stop()
        return False


# 全局监听器实例
_watcher: Optional[ConfigWatcher] = None


def get_watcher() -> ConfigWatcher:
    """
    获取全局监听器实例

    返回:
        ConfigWatcher 实例
    """
    global _watcher

    if _watcher is None:
        _watcher = ConfigWatcher(watch_paths=[])
        # 设置默认回调
        from heimaclaw.config.loader import reload_config

        def default_callback(path: Path):
            info(f"触发配置重载: {path}")
            reload_config()

        _watcher.set_callback(default_callback)

    return _watcher


def start_watcher(
    watch_paths: List[Path],
    extensions: Optional[Set[str]] = None,
    callback: Optional[Callable[[Path], None]] = None,
):
    """
    启动全局配置监听器

    参数:
        watch_paths: 要监听的目标路径列表
        extensions: 要监听的文件扩展名
        callback: 文件变化时的回调函数
    """
    watcher = get_watcher()

    if extensions:
        watcher.extensions.update(extensions)

    if callback:
        watcher.set_callback(callback)

    watcher.start()
    return watcher


def stop_watcher():
    """停止全局配置监听器"""
    global _watcher

    if _watcher:
        _watcher.stop()
        _watcher = None
