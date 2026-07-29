# 开发路线图与 Sprint 1

> 状态：Portfolio MVP Complete
>
> 版本：v1.0

本文把需求与架构基线拆分为可交付、可验证的工程迭代。每个迭代都必须形成可运行的软件增量，不以“写完若干文件”作为完成标准。

## 协作方式

为了同时完成项目和学习目标，工作按以下方式分配：

- Codex 负责重复性工程配置、示例讲解、任务拆分、代码评审和验证。
- 学习者亲手实现核心领域规则、Agent 节点和关键异步逻辑。
- 新知识在即将使用时通过小例子解释，不要求先阅读大段教程。
- 每个核心任务先明确输入、输出、不变量和验收测试，再开始编码。
- Codex 不直接替换学习者尚未提交评审的核心实现；发现问题时先解释证据和修改方向。

## 交付路线

| 迭代 | 可演示增量 | 关键知识 |
| --- | --- | --- |
| Sprint 1 | 可安装、可测试的领域项目骨架 | Python 工程结构、值对象、测试、类型检查、CI |
| Sprint 2 | 接收并校验一份旅行需求 | FastAPI、Pydantic、应用用例、错误映射 |
| Sprint 3 | 使用 Fake Model 生成并检查候选行程 | Agent 状态、节点契约、结构化输出、确定性规则 |
| Sprint 4 | 可确认、执行和取消规划任务 | LangGraph、Checkpoint、`asyncio`、取消传播 |
| Sprint 5 | 数据、版本与幂等基础设施 | PostgreSQL Schema、SQLAlchemy Async、迁移、幂等 |
| Sprint 6 | 接入真实模型与旅行工具 | Responses API、工具契约、并发 I/O、超时与重试 |
| Sprint 7 | 完成 Web 演示闭环 | React、轮询、错误与状态展示 |
| Sprint 8 | 建立评测、观测和部署证据 | 数据集契约、Trace、Docker、CI |

以上 Sprint 的 Portfolio MVP 增量已经交付。完整生产 Worker、局部修改闭环和全量行为 Eval 的状态以[实现状态](implementation-status.md)为准。

真实 OpenAI、天气、地点和路线服务在相应端口与 Fake 实现稳定后接入，避免外部依赖阻塞核心业务开发。

## Sprint 1 目标

建立一个任何开发者克隆后都能重复安装、检查和测试的 Python 3.12 项目，并完成第一组无网络、无数据库、无模型依赖的旅行领域对象。

当前工程基线支持 x86_64 macOS 本地开发环境和 x86_64 Linux CI、容器及部署环境；第一版不承诺 Windows 或其他处理器架构的本地开发兼容性。扩展平台支持时必须更新锁文件并通过对应 CI。

### Backlog

| 编号 | 任务 | 负责人 | 产物 | 状态 |
| --- | --- | --- | --- | --- |
| `S1-01` | 初始化 Python 包与模块目录 | Codex | `pyproject.toml`、`src/trippilot` | Done |
| `S1-02` | 建立格式、Lint、类型、测试、覆盖率与构建门禁 | Codex | 工具配置、锁文件、GitHub Actions | Done |
| `S1-03` | 实现 `Money` 值对象 | 学习者 | 金额模型及单元测试 | Done |
| `S1-04` | 实现 `TravelDateRange` 值对象 | 学习者 | 日期范围模型及单元测试 | Done |
| `S1-05` | 组合 `TravelRequest` 领域模型 | 学习者 + Codex | 需求模型及业务不变量测试 | Done |
| `S1-06` | 完成 Sprint 评审与回顾 | 共同 | 演示记录、问题与下一步 | Done |

以下任务描述作为项目学习复盘材料保留；实现代码和测试已经完成，可以按编号重新练习。

## S1-03：第一个编码任务

学习者将在 `src/trippilot/domain/value_objects/money.py` 中实现不可变的 `Money` 值对象，并在 `tests/unit/domain/value_objects/test_money.py` 中编写测试。

### 行为要求

- 金额使用 `Decimal`，不能使用 `float`。
- 币种第一版只接受 `CNY`。
- 金额不能为负数，允许零金额。
- 精度最多为小数点后两位。
- 相同币种的金额可以相加；结果仍为 `Money`。
- 对象创建后不能修改。
- 无效输入抛出明确的领域异常，不泄漏底层库异常。

### 验收示例

```python
Money(Decimal("12.30"), "CNY") + Money(Decimal("7.70"), "CNY")
```

结果应等于 `Money(Decimal("20.00"), "CNY")`。

以下输入必须被拒绝：

- `Decimal("-0.01")`
- `Decimal("1.001")`
- 币种 `USD`
- `float` 类型的 `12.3`

### 完成定义

- 正常、边界和异常行为都有测试。
- Ruff、mypy 和 pytest 全部通过。
- 分支覆盖率不低于项目门禁。
- 代码只依赖 Python 标准库和领域内部类型。
- 提交信息符合 `feat: 实现金额值对象` 格式。
- 代码评审中的问题已经解释并关闭。

## Sprint 1 完成标准

- 新环境可通过锁文件重复安装依赖。
- 本地检查与 GitHub Actions 使用相同命令。
- `domain` 不依赖 Web、数据库、模型或外部 SDK。
- `Money`、`TravelDateRange` 和 `TravelRequest` 的业务不变量具有自动测试。
- README 能让新开发者独立运行检查。
- 所有变更经过提交前检查和代码评审。

## `asyncio` 学习安排

Sprint 1 的领域代码刻意保持同步，因为纯计算不需要异步。`asyncio` 将分三次结合项目学习：

1. Sprint 2：理解 `async def`、等待 I/O 和 FastAPI 请求边界。
2. Sprint 4：理解任务、取消、超时和 LangGraph 异步恢复。
3. Sprint 6：使用 `TaskGroup` 并发调用独立旅行工具，并避免共享 `AsyncSession`。

每次只引入当前场景真正需要的概念，并通过测试观察运行行为。
