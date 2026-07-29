# 01：项目导览

## 先得到全局地图

TripPilot 是模块化单体，不是把所有逻辑写在 FastAPI 路由中：

| 层 | 目录 | 职责 |
| --- | --- | --- |
| Interface | `interfaces/http`、`web` | HTTP 契约、鉴权 Header、前端状态展示 |
| Application | `application`、`execution` | 用例编排、任务生命周期、幂等命令 |
| Agent | `agent` | 有限状态图、候选生成与重规划路由 |
| Domain | `domain` | 金额、需求、行程、不变量、预算和约束 |
| Ports | `ports` | 模型、工具、仓储抽象 |
| Infrastructure | `infrastructure` | Fake、OpenAI、HTTP、PostgreSQL、日志实现 |
| Bootstrap | `bootstrap` | 配置和依赖组装 |

### [必须掌握] 依赖方向

领域层不能导入 FastAPI、OpenAI、SQLAlchemy 或 LangGraph。业务规则如果依赖具体 SDK，就很难独立测试，也很难替换供应商。

端口是“业务需要什么能力”，适配器是“某个技术如何提供该能力”。例如：

- `PlacePort.search` 是稳定能力；
- `FakePlaceTool` 和 `AmapPlaceTool` 是两种实现；
- 工作流只依赖 `PlacePort`。

### [必须掌握] 一次请求如何流动

以创建规划为例：

1. `POST /api/v1/planning-tasks` 由 FastAPI 校验输入。
2. `TaskCoordinator.create` 调用 `RequirementService`。
3. Fake 或 OpenAI Extractor 返回 `RequirementDraft`。
4. 缺字段则进入 `COLLECTING_REQUIREMENTS`，完整则进入 `AWAITING_CONFIRMATION`。
5. 用户确认后，Coordinator 创建异步执行任务。
6. `PlanningWorkflow` 调用 LangGraph。
7. 图并发加载地点与天气，生成候选，运行确定性检查。
8. 通过则生成 `TripPlan`；硬约束失败则有限重规划；未知信息产生 `PARTIAL`。
9. 前端轮询任务并展示时间线、预算、约束和来源。

### [应该理解] 为什么先确认再规划

确认边界同时解决产品与工程问题：

- 避免基于错误日期、预算调用付费模型和工具；
- 让“用户说过什么”和“系统假设了什么”可见；
- 给任务建立稳定的 `TravelRequest` 快照；
- 方便重放、审计和评测。

## 第一次运行

```bash
uv sync
uv run uvicorn trippilot.interfaces.http.app:create_app --factory --reload
```

另一个终端：

```bash
cd web
npm ci
npm run dev
```

访问 `http://localhost:5173`。默认 Fake 模式不需要密钥、不产生模型费用。

## 自检问题

1. 为什么 `Money` 使用 `Decimal` 而不是 `float`？
2. 为什么 HTTP Schema 不直接等于领域模型？
3. 为什么真实与 Fake 工具必须通过相同端口？
4. 创建任务为什么返回令牌而不是数据库自增 ID？
5. 从哪个文件可以找到应用全部依赖的组装位置？
