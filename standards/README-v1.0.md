# standards/ 使用说明（通用脚手架）

这个文件夹是任意软件项目的“第二大脑”。

新项目使用流程：
1. 复制整个 standards/ 到项目根目录
2. 根据项目类型修改包名、模块名
3. 新会话开始时，提供：
   - PROJECT-STATUS.md
   - PROJECT-DECISION-LOG.md（最近5条）
   - KNOWLEDGE-CHECK-CHECKLIST.md 回答
   - CLI-COMMANDS-v1.0.md（终端命令清单）

支持扩展为“子模块工厂”模式（可选）：
- 可自行实现 project-cli submodule create <name>
- 自动复制 standards/ 并替换关键字段

所有项目均可复用，无需修改规范本身。