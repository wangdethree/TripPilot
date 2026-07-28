# 技术选型

> 状态：In Review
>
> 候选基线：v1.0
>
> 调研日期：2026-07-28

技术选型以架构驱动因素、学习成本、可测试性和演示完整度为依据。具体补丁版本由锁文件固定，架构文档只固定需要评审的产品和主要版本族。

## 选型结果

| 领域 | 选择 | 用途 |
| --- | --- | --- |
| 服务端语言 | Python 3.12 | Agent、API、领域规则、工具和评测 |
| Python 项目管理 | uv + `pyproject.toml` + `uv.lock` | Python 安装、依赖解析、虚拟环境和锁定 |
| HTTP API | FastAPI + Uvicorn | 异步 REST API、OpenAPI 和依赖装配入口 |
| Schema | Pydantic v2 | API DTO、模型结构化输出、工具契约和配置 |
| Agent 工作流 | LangGraph `StateGraph` | 显式节点、条件路由、中断、恢复和检查点 |
| 模型接入 | OpenAI Python SDK + Responses API | 真实需求提取和候选计划生成 |
| 数据库 | PostgreSQL 18 | 任务、行程版本、缓存、执行元数据和检查点 |
| 数据访问 | SQLAlchemy 2.x Async + psycopg 3 | 异步仓储与事务 |
| 数据迁移 | Alembic | 可审查、可回滚的数据库迁移脚本 |
| 外部 HTTP | HTTPX Async | 天气、地点、路线和模型以外的 HTTP 集成 |
| 可观测性 | OpenTelemetry Trace/Metric + JSON 日志 | 跨节点 Trace、指标和脱敏结构化日志 |
| 服务端测试 | pytest + pytest-asyncio + Hypothesis | 单元、异步、属性、契约和集成测试 |
| Python 质量 | Ruff + mypy + coverage.py | 格式、静态检查、类型和覆盖率 |
| 前端 | React + TypeScript + Vite | 需求确认、任务状态和行程展示 |
| 前端运行时 | Node.js 24 LTS | 构建和测试前端 |
| 本地环境 | Docker Compose | PostgreSQL、服务端和前端的一致运行环境 |
| CI | GitHub Actions | 检查、测试、评测、构建和安全扫描 |

## 服务端基础

### Python 3.12

Python 3.12 在异步、类型和性能方面足够现代，同时比更新的解释器版本具有更宽的第三方库兼容窗口。本地系统当前的 Python 3.11 不构成阻塞，uv 可以按项目配置安装并选择 Python 3.12。

项目将使用：

```text
.python-version
pyproject.toml
uv.lock
```

CI 和容器必须读取相同版本约束，禁止各环境手工维护不同的 `requirements.txt`。

### uv

uv 负责 Python 版本、依赖、虚拟环境和锁文件。CI 使用 `uv sync --locked` 或等价锁定模式，依赖升级通过独立提交完成。

选择原因：

- 可以自动获取项目要求的 Python 版本。
- `uv.lock` 固定完整依赖图。
- 本地、CI 和容器使用相同依赖来源。
- 开发依赖可以通过 dependency groups 管理。

### FastAPI

FastAPI 只承担接口层职责：

- HTTP 路由与 OpenAPI
- Pydantic 请求响应
- 鉴权令牌提取
- 应用用例调用
- 稳定错误映射

正式规划任务不使用 FastAPI `BackgroundTasks` 作为唯一执行机制。官方文档将其定位于响应后的小型任务，并指出重型、多进程任务需要更强的任务机制。TripPilot 使用持久化任务记录和执行器。

## Agent 工作流

### LangGraph `StateGraph`

LangGraph 与 ADR-0003 的显式状态图一致，提供：

- 节点和条件路由
- 持久化检查点
- `interrupt()` 暂停并等待用户确认
- 使用相同 `thread_id` 恢复
- 故障后从检查点继续
- 异步 `ainvoke` / `astream` 能力

第一版使用 LangGraph 核心工作流能力，不使用预置的自由 ReAct Agent，也不使用多 Agent。

工作流状态只保存恢复所需的结构化数据和引用，不把完整数据库对象、SDK 客户端或大段原始对话放入 Checkpoint。

### 为什么不自研完整工作流引擎

自研状态机容易完成节点路由，但持久化中断、恢复、并发执行语义和检查点兼容会占用大量开发时间。使用 LangGraph 可以把学习重点放在 Agent 状态、节点契约、幂等和评测上。

### 为什么不使用 OpenAI Agents SDK

OpenAI Agents SDK 适合工具调用、Tracing 和 Agent handoff，但 TripPilot 当前只需要单 Agent 显式状态图。同时使用两套 Agent 运行时会产生重复的状态、Trace 和工具抽象。

TripPilot 因此使用：

- LangGraph：工作流运行时
- OpenAI SDK：`ModelPort` 的一个基础设施适配器

未来如果需求出现多 Agent handoff，再通过 ADR 评估 Agents SDK。

## 模型接入

### Responses API

真实 OpenAI 适配器使用 Responses API。模型输出通过 Pydantic Schema 生成严格结构化输出，系统仍会再次执行本地 Schema 与领域校验。

开发和自动测试默认使用：

- `FakeRequirementExtractor`
- `FakePlanGenerator`
- 固定模型响应 Fixture

因此，没有 API Key 也能完成领域、工作流和绝大部分集成测试。

### 模型配置

模型名称不写死在领域或工作流代码中。初始真实集成评测配置为：

| 任务 | 起始模型 | 起始推理强度 | 说明 |
| --- | --- | --- | --- |
| 需求提取与澄清 | `gpt-5.6-luna` | `low` | 结构明确、调用频率高，优先控制成本与延迟 |
| 候选计划与重规划 | `gpt-5.6-terra` | `medium` | 在规划质量、延迟和成本之间平衡 |
| 可选人工评测辅助 | `gpt-5.6-terra` | `medium` | 只提供辅助评分，最终结论由人工确认 |

这些是评测起点，不是永久绑定。发布候选版本必须记录实际模型、模型返回版本、Prompt 版本和推理配置，并通过同一数据集比较后才能调整。

默认设置 `store: false`，由 TripPilot 自己管理业务状态和最小上下文。是否满足更严格的数据保留策略还需要结合实际 OpenAI 账户和数据控制配置验证。

### 结构化输出

- 需求提取和计划生成使用 Pydantic 模型生成 JSON Schema。
- 使用 Structured Outputs，不使用只有“合法 JSON”保证的 JSON Mode。
- 可选模型工具请求使用严格函数 Schema。
- 即使供应商返回结构化对象，也必须再次执行本地 Pydantic 与领域校验。
- Refusal、截断、超时和无法解析分别映射为结构化错误。

## 数据与任务执行

### PostgreSQL 18

PostgreSQL 同时支持关系型约束、事务、行级锁和 JSONB，适合任务元数据与不可变行程文档的混合存储。

第一版不引入 Redis、RabbitMQ 或独立 Celery 集群。服务端执行器通过 PostgreSQL 任务记录、租约和 `FOR UPDATE SKIP LOCKED` 协调任务。

引入独立消息队列的重新评估条件：

- 数据库轮询成为经过测量的瓶颈。
- 需要大规模多进程或多机器执行。
- 需要不同任务类型的独立扩缩容与优先级。
- 任务吞吐明显超过当前 10 并发目标。

### SQLAlchemy 与会话边界

- 使用 SQLAlchemy 2.x 异步 API。
- 每个请求或并发任务创建独立 `AsyncSession`。
- 不在 `asyncio.gather()` 的多个任务之间共享同一 Session。
- 应用层通过 `UnitOfWork` 控制提交与回滚。
- Alembic 迁移脚本必须进入代码评审，禁止运行时自动修改 Schema。

### JSONB 使用边界

关系列保存需要筛选、排序、唯一约束和并发更新的数据；JSONB 保存按版本原子读取的嵌套需求与行程文档。

禁止把所有字段无差别存入一个 JSONB 列，也禁止为了“关系化”而把每个时间线详情拆成大量难以版本化的表。

## 可观测性

- OpenTelemetry 用于 Trace 和 Metric。
- JSON 应用日志单独输出到标准输出。
- 当前 OpenTelemetry Python 的 Trace 和 Metric 为稳定能力；日志信号仍处于开发状态，因此第一版不依赖 OTel Logs 作为唯一日志方案。
- 本地默认使用控制台或测试导出器。
- 演示环境通过 OTLP 配置接入具体后端，业务代码不依赖后端厂商。

LangSmith 可以在开发阶段作为可选的 LangGraph 调试工具，但不作为运行、验收或故障恢复的必要依赖。

## 前端

React + TypeScript + Vite 负责构建独立 Web 客户端：

- TypeScript 对 API DTO 和状态渲染提供静态检查。
- Vite 提供轻量开发和生产构建。
- Node.js 使用当前 LTS 24，不使用本机当前的 Node.js 26 Current 版本作为项目基线。
- 前端通过生成或校验 OpenAPI 类型减少接口漂移。

Agent、领域和工作流仍是学习重点。前端只实现完成产品演示所需的交互，不引入复杂状态框架。

## 测试与质量

### 测试分层

| 层级 | 依赖 | 主要内容 |
| --- | --- | --- |
| 领域单元测试 | 无网络、数据库、模型 | 金额、日期、时间线、约束、状态和版本 |
| 属性测试 | Hypothesis | 日期范围、金额不变量、版本与状态组合 |
| 工作流测试 | Fake Model + Fake Tools + 内存 Checkpoint | 节点路由、中断、取消和重规划 |
| 契约测试 | 端口 Fixture | 模拟与真实适配器输出一致性 |
| 数据集成测试 | PostgreSQL | 事务、租约、幂等、版本冲突和删除 |
| API 测试 | 完整服务端 + Fake 外部能力 | HTTP 状态、令牌和用例闭环 |
| Agent 评测 | 版本化场景集 | 提取、工具、计划质量与回归 |

### CI 门禁

- Ruff format 与 lint
- mypy
- pytest 与覆盖率
- 数据库迁移检查
- Agent 回归评测
- 前端 lint、类型检查、单元测试与构建
- 依赖漏洞和密钥扫描
- Docker 构建

## 官方资料依据

- [OpenAI 模型与 Responses API 指引](https://developers.openai.com/api/docs/guides/latest-model)
- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [OpenAI Function Calling](https://developers.openai.com/api/docs/guides/function-calling)
- [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [FastAPI Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/)
- [SQLAlchemy Session 与 AsyncSession 并发边界](https://docs.sqlalchemy.org/en/20/orm/session_basics.html)
- [Pydantic Strict Mode](https://pydantic.dev/docs/validation/latest/concepts/strict_mode/)
- [Pydantic JSON Schema](https://pydantic.dev/docs/validation/latest/concepts/json_schema/)
- [PostgreSQL 18 JSONB](https://www.postgresql.org/docs/18/datatype-json.html)
- [PostgreSQL 18 SELECT 锁定](https://www.postgresql.org/docs/18/sql-select.html)
- [uv 锁定与同步](https://docs.astral.sh/uv/concepts/projects/sync/)
- [OpenTelemetry Python](https://opentelemetry.io/docs/languages/python/)
- [Node.js 发布状态](https://nodejs.org/en/about/previous-releases)
- [Vite Getting Started](https://vite.dev/guide/)
