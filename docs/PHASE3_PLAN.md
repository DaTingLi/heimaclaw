# Phase 3: 热重载

## 目标
实现配置文件热加载，修改配置后无需重启服务。

## 功能
1. **文件监听** - 使用 inotify 监控配置文件变化
2. **增量编译** - Markdown 配置变更后自动重新编译
3. **配置重载** - 无需重启，自动加载新配置

## 实现方案

### 1. 文件监听 (src/heimaclaw/config/watcher.py)
- ConfigWatcher 类
- 使用 watchdog 库监控文件变化
- 回调机制通知配置变更

### 2. Markdown 编译器增量模式
- 新增 `compiler.py` 的增量编译方法
- 监听 `.md` 文件变化，自动触发编译

### 3. 配置重载集成
- 在 `loader.py` 添加热重载支持
- 通知相关模块配置已更新

## 依赖
- watchdog>=3.0 (文件监听)

## 测试
- 48 existing tests must pass
- Add watcher tests

## 状态
- [x] 计划完成
- [ ] 实现中
- [ ] 测试通过
