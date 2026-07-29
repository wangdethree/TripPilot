# ADR-0004：使用 LangGraph 作为工作流运行时

> 状态：Accepted
>
> 日期：2026-07-28

## 背景

ADR-0003 已决定使用显式状态图。TripPilot 还需要持久化检查点、等待用户确认、异步恢复、失败重试和执行过程观测。自研完整运行时会把大量精力投入到状态持久化与恢复基础设施。

## 决策

使用 LangGraph `StateGraph` 实现 TripPilot Agent 工作流，并使用 PostgreSQL 异步 Checkpointer 保存工作流检查点。

- 使用显式节点和条件边，不使用预置的自由 ReAct 循环。
- 使用 `interrupt()` 实现需求确认和需要用户决策的暂停点。
- 内部任务 UUID 作为 `thread_id`。
- 业务状态、行程版本和访问控制仍由 TripPilot 业务表负责。
- 节点只接收可序列化状态，不保存 SDK 客户端、数据库会话或密钥。
- 模型和工具调用封装为可追踪、幂等或可安全重试的节点任务。

## 备选方案

### 自研状态机与 Checkpoint

依赖更少，但需要自行解决中断恢复、并发写入、Checkpoint 兼容和调试能力。

### OpenAI Agents SDK

具备工具、Tracing 和 handoff 能力，但当前单 Agent 显式流程不需要 handoff，同时使用会与 LangGraph 重复管理运行状态。

### Celery Canvas

适合分布式任务编排，但对用户交互式中断、图状态查看和 Agent 节点语义支持不如专用工作流运行时直接。

## 影响与后果

- 团队需要学习 LangGraph State、Node、Edge、Checkpoint、Interrupt 和恢复语义。
- 工作流状态 Schema 成为需要版本管理的内部契约。
- 节点在恢复时可能重新执行，因此副作用必须幂等。
- LangGraph 升级需要运行完整工作流回归测试。
- 业务逻辑继续放在领域和应用模块，避免框架锁定扩散。
