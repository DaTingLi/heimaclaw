# 通用软件项目开发规范 v1.0（模块化 + 文档驱动 + AI 协作脚手架）

## 设计哲学
1. 任务驱动而非日期驱动
2. 一切皆模块，一切皆接口
3. 文档即代码的第二大脑
4. 上下文可恢复性优先于开发速度
5. 任何项目都应能在 30 分钟内被任意 AI / 新开发者完全理解当前状态

## 适用范围
- 本规范适用于任何 Python 项目（AI Agent、Web 服务、CLI 工具、数据管道、学生项目、企业系统等）
- 可作为独立脚手架使用：直接复制 standards/ 文件夹到任意新项目根目录
- 支持扩展为“子模块工厂”模式（可选）：通过自定义命令批量生成子模块 / 子项目

## 使用方式
1. 新建项目时，直接复制整个 standards/ 文件夹到项目根目录
2. 根据项目类型替换包名、模块名（无需修改规范本身）
3. 每次会话开始，优先提供：
   - PROJECT-STATUS.md 最新内容
   - PROJECT-DECISION-LOG.md 最近 5 条
   - KNOWLEDGE-CHECK-CHECKLIST.md 回答

## 进度管理规则
- 禁止使用“Day X”作为进度标识
- 所有进度记录在 PROJECT-STATUS.md 中，以模块 + 子任务 + 接口完成度为单位
- 每次会话结束，必须更新 PROJECT-STATUS.md

## 会话恢复机制
1. 新会话开始时，开发者必须先提供：
   - PROJECT-STATUS.md 最新内容
   - PROJECT-DECISION-LOG.md 最近 5 条
   - 当前要开发的模块/任务名称
2. AI 必须在 60 秒内确认已理解全局状态

## 模块化原则
见 MODULE-INTERFACE-STANDARD.md

## 子模块 / 子项目生成规则（可选扩展）
1. 可选命令示例：project-cli submodule create <name> --type agent --channel feishu
2. 创建时自动复制 standards/ 并做替换（包名、模块名等）
3. 目的：确保每个子模块天生具备统一的开发规范、接口体系、文档模板、进度管理机制

版本：v1.0