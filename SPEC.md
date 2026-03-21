# SPEC.md - Subagent 分派机制 + 任务分解规划器

**版本**: v1.0
**创建日期**: 2026-03-20
**状态**: 进行中

---

## 1. 背景与目标

### 问题
当前 HeiMaClaw 的 ReAct 引擎：
1. **工具执行后让 LLM 自行决定下一步** — 导致决策不够智能
2. **所有任务在主 Agent 执行** — 上下文膨胀，工具调用重复
3. **缺乏任务分解** — 复杂任务没有拆分为步骤
4. **SubagentSpawner 已实现但未使用** — 无法并行执行子任务

### 目标
1. **任务分解规划器（Planner）** — 在执行前将复杂任务拆解为步骤
2. **Subagent 分派机制** — 将子任务分派给独立 Agent 执行
3. **智能工具选择** — 避免重复调用相同工具

---

## 2. 架构设计

### 2.1 整体架构

```
用户消息 → Planner(分解任务) → 生成执行计划 → 按计划执行
                                              ↓
                              ┌───────────────┴───────────────┐
                              ↓                               ↓
                    直接执行工具                    SubagentSpawner 分派
                    (direct mode)                  (subagent mode)
```

### 2.2 关键接口

**ExecutionStep**:
```python
@dataclass
class ExecutionStep:
    step_id: str           # 步骤 ID
    description: str       # 步骤描述
    tool_name: str         # 要使用的工具
    parameters: dict      # 工具参数
    depends_on: list[str]  # 依赖的步骤 ID
    execution_mode: str    # "direct" | "subagent"
```

---

## 3. 实现计划

### Phase 1: Planner 实现
- 创建 src/heimaclaw/agent/planner.py
- 实现任务分析逻辑
- 实现步骤生成逻辑

### Phase 2: ReAct 引擎改造
- 在 execute() 方法中调用 Planner
- 支持直接执行和 Subagent 两种模式

### Phase 3: Subagent 集成
- 将 SubagentSpawner 集成到 ReAct 引擎
- 实现结果汇总逻辑
