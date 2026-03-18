# 新子模块 / 子项目创建模板（复制 standards/ 后使用）

1. 可选命令示例：project-cli submodule create <name> --type agent --channel feishu
2. 系统自动完成：
   - 复制 standards/ 到新子目录
   - 生成 config.toml
   - 初始化 PROJECT-STATUS.md
   - 创建 SPEC.md（基于模板）
3. 后续手动步骤：
   - 编辑 config.toml 填入必要信息
   - 根据类型设置相关配置
4. 完成创建后运行：project-cli submodule test <name>