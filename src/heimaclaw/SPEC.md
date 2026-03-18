# CLI 模块 Spec 文档 v1.0

## 1. 概述与目标
- **项目/模块名称**：HeiMaClaw CLI 模块
- **业务/功能目标**：提供统一的命令行接口，驱动 HeiMaClaw 所有功能
- **范围**：
  - 包含：CLI 命令定义、参数解析、交互式配置向导
  - 不包含：具体业务逻辑实现（由其他模块提供）

## 2. 需求来源与约束
- **来源文档**：DEVELOPMENT-NORM-v1.0.md
- **性能要求**：CLI 启动时间 < 100ms
- **安全/合规要求**：敏感信息（API Key）不直接显示在日志中
- **时间窗口**：Phase 1 - 核心骨架

## 3. 系统架构
- **分层图**：
  ```
  CLI (cli.py)
    ├── 命令定义层：init, start, status, doctor, config, agent, channel
    ├── 参数解析层：Typer
    ├── 输出层：Rich Console
    └── 业务调用层：ConfigLoader, AgentManager, ChannelAdapter
  ```
- **技术选型**：
  - Typer：CLI 框架
  - Rich：终端输出
  - tomli/tomli-w：配置文件读写
- **关键依赖**：typer>=0.9.0, rich>=13.0.0

## 4. 数据模型
- **核心实体**：
  - AgentConfig：Agent 配置
  - ChannelConfig：渠道配置
  - ServerConfig：服务配置
- **字段说明**：见 interfaces.py

## 5. 接口设计
- **主要命令**：
  | 命令 | 功能 | 参数 |
  |------|------|------|
  | init | 初始化项目 | --path, --force |
  | start | 启动服务 | --host, --port, --workers, --reload |
  | status | 显示状态 | 无 |
  | doctor | 环境诊断 | 无 |
  | config show | 显示配置 | [key] |
  | config set | 设置配置 | <key> <value> |
  | config edit | 编辑配置 | 无 |
  | agent create | 创建 Agent | <name> --channel --description |
  | agent list | 列出 Agent | 无 |
  | channel setup | 配置渠道 | <channel> |

- **错误码表**：
  | 退出码 | 含义 |
  |--------|------|
  | 0 | 成功 |
  | 1 | 通用错误 |
  | 2 | 参数错误 |
  | 130 | 用户中断（Ctrl+C） |

## 6. 关键流程
- **init 命令流程**：
  1. 确定项目路径（默认 /opt/heimaclaw）
  2. 检查目录是否存在
  3. 创建子目录结构（config, logs, data, sandboxes）
  4. 生成默认 config.toml

- **agent create 命令流程**：
  1. 验证 Agent 名称唯一性
  2. 创建 Agent 目录
  3. 生成 agent.json 配置
  4. 提示下一步操作

## 7. 安全设计
- **鉴权**：CLI 运行需要系统用户权限
- **输入校验**：Agent 名称仅允许字母、数字、中划线、下划线
- **敏感信息**：app_secret、api_key 等使用 hide_input=True 输入

## 8. 性能与可扩展性
- **瓶颈点**：无（CLI 为轻量级操作）
- **扩容方案**：子命令通过 Typer.add_typer 动态注册

## 9. 测试策略
- **单元测试覆盖**：
  - 各命令的参数解析
  - 输出格式验证
  - 错误处理
- **E2E 测试场景**：
  - 完整的 init -> config -> agent create 流程

## 10. 部署与运维
- **容器化**：通过 pip install 安装
- **监控指标**：无（CLI 工具）

## 11. 风险与备选方案
- **主要风险**：Typer 版本兼容性
- **备选方案**：可切换到 click 直接使用

## 12. 附录
- **参考资料**：
  - Typer 文档：https://typer.tiangolo.com/
  - Rich 文档：https://rich.readthedocs.io/
- **决策记录**：决策 005（CLI 框架选型）

版本：v1.0
