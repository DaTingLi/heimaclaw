# 上线前极客级别代码审计报告 (Pre-launch Audit Report)

**审计日期**: 2026-03-25
**审计目标**: `heimaclaw` 项目核心代码库 (`src/heimaclaw/` 及 `tests/`)
**审计结论**: 🚫 **严重阻断，不可直接上线 (NOT READY FOR PRODUCTION)**

经对代码库的系统级审计，本项目在安全防御、架构完整度、运行时稳定性和代码质量上存在严重缺陷。虽然实现了框架骨架，但在**生产环境**下将面临被恶意攻击、文件越权访问和功能断层等严重风险。

---

## 🛑 1. 致命级安全漏洞 (Critical Security Issues)

### 1.1 飞书 Webhook 签名验证缺失 (CWE-345)
- **代码位置**: `src/heimaclaw/channel/feishu.py` 行 123-125
- **问题描述**: 在 Webhook 处理逻辑中，`# TODO: 实现签名验证` 被直接使用 `pass` 跳过。
- **业务影响**: 攻击者可以伪造飞书官方请求，向 Webhook 接口发送任意载荷，直接触发后端的 AI Agent 执行任意代码或操作内部数据。
- **具体解决方案**:
  1. 必须根据飞书开放平台文档，获取 `X-Lark-Request-Timestamp` 和 `X-Lark-Request-Nonce`。
  2. 使用配置中的 `Encrypt Key` 对请求体进行 SHA256 签名计算。
  3. 比对计算的签名与 `X-Lark-Signature`，不匹配则立即返回 HTTP 403。

### 1.2 沙箱文件系统越权风险与执行崩溃 (CWE-22) - ✅ 已于 2026-03-25 修复
- **代码位置**: `src/heimaclaw/agent/docker_deepagents_backend.py` / `src/heimaclaw/sandbox/docker.py`
- **问题描述**: 原逻辑中，大模型文件读写落盘在宿主机，而执行容器内的 Shell 时引发了极其严重的路径错位与异步死锁崩溃。且底层调用缺乏 Shell 转义，导致复杂 Bash 语法全数报错（`exit=2`）。
- **业务影响**: 恶意指令可通过 fallback 逻辑越权突破到宿主机执行高危命令。
- **修复方案**: 
  1. 彻底移除了 `_local_execute` 这个极其危险的本地越权降级方法，所有报错直接截断返回大模型。
  2. 加入了 `asyncio.set_event_loop(loop)` 解决了挂起的并发死锁。
  3. 通过引入 `shlex.quote(command)`，使得复杂指令在通过 Docker `exec` 时获得了免疫 Bash 转义错乱的护甲。
  4. 完全对齐了 `root_dir` 挂载路径。

---

## ⚠️ 2. 核心架构功能断层 (Architectural Breakages)

### 2.1 Event Bus 虚假集成
- **代码位置**: `src/heimaclaw/agent/runner.py` 行 41
- **问题描述**: `PROJECT-STATUS-v1.0.md` 宣称 Event Bus 已经 100% 完成并集成，但实际代码中为：`# from heimaclaw.core.event_bus import EventBus, Event, EventType  # 暂时禁用 EventBus`。
- **业务影响**: 宣称的事件驱动架构实际上并未在 Agent 的主循环中起效，导致组件间耦合退化为同步调用，丧失了状态解耦和高级事件追踪能力。
- **具体解决方案**:
  1. 移除 `runner.py` 中的注释，将 `AgentRunner` 的状态流转真正接入 `EventBus`。
  2. 修复导致临时禁用 Event Bus 的底层 bug（推测为阻塞或序列化报错）。

### 2.2 硬件沙箱（Firecracker）功能残缺
- **代码位置**: `src/heimaclaw/sandbox/firecracker.py` 行 336, 590, 610, 619
- **问题描述**: 大量核心虚拟化生命周期方法（快照创建、快照恢复、暂停、恢复）均标记为 `# TODO` 并直接抛出异常或仅输出日志。
- **业务影响**: 在长期运行或高负载场景下，无法实现沙箱的状态持久化与热迁移。如果上层服务调用了这些接口，会导致整个流程崩溃。
- **具体解决方案**:
  1. 补齐 `Firecracker` 的 API 调用，实现完整的 `/machine-config` 和 `/snapshot/create` HTTP PUT 请求。
  2. 若短期内无法实现，应在方法内抛出 `NotImplementedError`，并在上层调度（Planner/Runner）中增加降级逻辑（Fallback）。

---

## 🐞 3. 运行时稳定性与监控 (Stability & Monitoring)

### 3.1 监控探针伪造 (Fake Health Checks)
- **代码位置**: `src/heimaclaw/server_monitoring.py` 行 37-41
- **问题描述**: 就绪检查端点（Readiness Probe）写死返回 `{"database": "ok", "llm": "ok"}`，实际毫无探测逻辑 (`# TODO: 检查数据库连接、LLM 连接等`)。
- **业务影响**: K8s 或其他负载均衡器会认为服务永远健康，即使数据库或 LLM API 断连也会不断打入流量，导致线上大面积 500 错误。
- **具体解决方案**:
  1. 实现真实的 Ping 探针：对数据库执行 `SELECT 1`。
  2. 对 LLM Provider 实现轻量级的模型列表拉取（如 `v1/models`）测试连接。

### 3.2 异常吞没 (Swallowed Exceptions)
- **代码位置**: 全局多处，特别是 `src/heimaclaw/cli.py` (如 590 行、2231 行等)
- **问题描述**: 存在大量 `except Exception: pass` 或空 `except` 代码块。
- **业务影响**: 严重错误被静默吞没，线上排障将如同盲人摸象，根本无法定位到 OOM、网络超时或权限问题。
- **具体解决方案**:
  1. 将空 `pass` 替换为 `logging.exception("...")` 或引入 Sentry 记录堆栈。
  2. 捕获具体的异常类型（如 `requests.exceptions.Timeout`）而不是宽泛的 `Exception`。

---

## 📊 4. 工程质量与测试 (Engineering Quality)

- **极低的代码测试覆盖率**: 经测试，核心代码（10151 行）的测试覆盖率仅为 **14%**。至关重要的 `runner.py`、`server.py` 和各类 `sandbox` 后端覆盖率为 **0%**。
- **严重的代码异味 (Code Smells)**: `ruff check` 报告超过 1700+ 个警告和错误，包含大量未使用导入、代码超长和无效逻辑。

### 能否完整正常运转？
**完全不能。** 当前代码仅仅是一个 **MVP（最小可行性产品）草稿**。在单机理想测试环境下或许能跑通基本的问答（Happy Path），但绝不能直接推向线上。

### 行动建议 (Action Plan)
1. **P0**: 立即修复飞书 Webhook 签名逻辑，防止未授权 RCE。
2. **P0**: 补充针对 `DockerDeepAgentsBackend` 的目录穿越防御机制。
3. **P1**: 完善健康检查 `/health`，确保上线后运维能监控到真实的系统存活状态。
4. **P1**: 真实接入 Event Bus 逻辑，修复系统架构设计与实现的背离。
5. **P2**: 将测试覆盖率从 14% 提升至至少 60%，特别是核心调度链路 `AgentRunner`。