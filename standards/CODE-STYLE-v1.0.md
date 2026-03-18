# 代码风格与日志规范 v1.0

## 1. 通用原则
- 代码必须清晰、专业、可维护、可搜索
- 所有输出（注释、日志、文档）优先使用**简体中文**（除代码本身、变量名、英文术语外）
- 禁止在代码、注释、字符串常量中出现任何 emoji（😊🚀等）
  - 理由：兼容性差、可读性低、搜索干扰、专业性不足
  - 检查方式：Code Review 时必须扫描 emoji

## 2. 日志规范（强烈推荐使用颜色区分）
日志是生产级项目最重要的可观测性手段，必须支持：

### 2.1 日志级别与颜色映射（终端输出）
- DEBUG：灰色（grey50 / dim）
- INFO：青色（cyan）
- SUCCESS：绿色加粗（green bold）
- WARNING：黄色加粗（yellow bold）
- ERROR：红色加粗（red bold）
- CRITICAL：品红加粗 + 白底（magenta bold on white）
- AGENT / SANDBOX 特殊事件：蓝色加粗（blue bold）或品红（magenta）

示例（使用 rich）：
```python
from rich.console import Console
from rich.theme import Theme

console = Console(theme=Theme({
    "debug": "grey50 italic",
    "info": "cyan",
    "success": "green bold",
    "warning": "yellow bold",
    "error": "red bold",
    "critical": "magenta bold on white",
    "agent": "blue bold",
    "sandbox": "magenta",
}))
```

### 2.2 日志输出规则

- **终端输出**：使用 rich，支持颜色、样式、表格、进度条

- **文件日志**：使用标准 logging 模块，纯文本、无颜色（JSON 结构化可选）

- **环境适配**：检测 os.getenv("NO_COLOR") 或 !sys.stdout.isatty() 时自动禁用颜色

- 结构化日志

  ：生产环境建议输出 JSON 格式，便于 ELK / Loki 收集 示例：

  Python

  ```
  import logging
  import json
  
  logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
  logger = logging.getLogger(__name__)
  
  # 终端用 rich，文件用 logging
  if sys.stdout.isatty():
      console.log("[error]启动失败", style="error")
  else:
      logger.error(json.dumps({"event": "start_failed", "reason": "port occupied"}))
  ```

### 2.3 日志内容要求

- 必须包含：时间、级别、模块名、事件描述、关键参数
- 禁止：纯中文口语化（如“哎呀出错了”），必须专业化
- 关键事件（如 Agent 创建、microVM 启动/失败）必须高亮（颜色 + 结构）

## 3. 注释规范

- 语言：**所有注释一律使用简体中文**

- 风格：Google 风格 docstring + 单行注释

- 函数/类上方：多行 docstring

  Python

  ```
  def create_microvm(agent_id: str) -> str:
      """
      创建一个独立的 microVM 实例，用于 Agent 隔离执行。
  
      参数:
          agent_id (str): Agent 的唯一标识符，用于命名和追踪
  
      返回:
          str: 创建成功的 microVM ID
  
      异常:
          MicroVMCreateError: 创建失败（资源不足、KVM 未启用等）
          TimeoutError: 启动超时
  
      示例:
          vm_id = create_microvm("sales-bot-001")
      """
      ...
  ```

- 行内注释：说明“为什么这么写”，而非“做了什么”

  Python

  ```
  # 优先从预热池获取，避免冷启动延迟（核心性能优化点）
  if self.warm_pool:
      vm = self.warm_pool.claim()
  ```

## 4. 其他风格约束

- 命名：PEP8（snake_case 函数、CamelCase 类）
- 缩进：4 空格
- 行长：不超过 88 字符（黑格式默认）
- 导入：标准库 → 第三方 → 本地，字母排序
- 异常处理：捕获具体异常，不要裸 except
- 字符串：优先 f-string，禁止 % 格式化

版本：v1.0



