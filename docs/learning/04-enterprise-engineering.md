# 04：企业级 Agent 工程化

“企业级”不是目录多，而是关键风险有明确契约、失败语义和验证证据。

## [必须掌握] 分层与依赖反转

领域规则稳定，供应商和框架容易变化。因此：

- Domain 只表达旅行规则；
- Application 编排用例；
- Ports 定义需要的能力；
- Infrastructure 实现 OpenAI、高德、Open-Meteo、PostgreSQL；
- Bootstrap 决定当前环境使用哪套实现。

这使 Fake 与真实服务可以切换，也让测试不需要密钥。

## [必须掌握] 配置与密钥

配置使用 `TRIPPILOT_` 前缀和 Pydantic Settings。密钥只从环境读取：

- 仓库只提交 `.env.example`；
- 日志处理器按敏感字段名脱敏；
- HTTP 错误不返回堆栈或供应商原文；
- Token 由安全随机源生成，服务端保存摘要。

## [必须掌握] 幂等与乐观并发

它们解决不同问题：

- `Idempotency-Key`：客户端超时重试时，相同命令不会重复产生副作用；
- `ETag` / `If-Match`：客户端基于旧版本修改时，不会覆盖新状态。

同一幂等键与相同请求返回第一次结果；同一键与不同请求返回冲突。原始键不写日志，Store 使用摘要。

## [必须掌握] 数据库迁移

SQLAlchemy 模型描述当前数据结构，Alembic 迁移描述如何从旧版本到新版本。生产发布不能在每个应用副本启动时自动抢着迁移，而应由一次性迁移 Job 完成。

TripPilot Schema 展示了：

- 任务和租约；
- 不可变行程版本；
- 幂等记录；
- 结构化事件；
- 乐观 `row_version`；
- Worker 用 `SKIP LOCKED` 安全认领任务。

## [应该理解] 可观测性

日志、Trace、Metric 回答不同问题：

- 日志：发生了什么业务事件；
- Trace：一次请求跨 API、Agent 节点、模型、工具经历了什么；
- Metric：成功率、延迟、成本是否整体异常。

TripPilot 为每次 HTTP 请求生成 `trace_id`，输出 JSON 结构日志并接入 FastAPI OpenTelemetry Instrumentation。日志不记录 Authorization、Token、API Key 和请求正文。

## [应该理解] 可靠性降级

不是所有依赖失败都必须让任务 `FAILED`：

- 地点无结果：没有规划事实基础，失败；
- 天气不可用：仍能提供基础路线，但明确未知，`PARTIAL`；
- 硬约束多次无法满足：`NEEDS_USER_INPUT`；
- 用户取消：`CANCELLED`；
- 未分类异常：转换成稳定 `INTERNAL_ERROR`，不泄漏内部细节。

## [拓展了解] 从组合模式到生产多进程

当前可演示版本由单个 API 进程执行异步任务，PostgreSQL 模型、迁移和租约算法已经实现并独立测试。真正水平扩展时，还要把 Coordinator 换成持久化任务仓储和独立 Worker，并接入 PostgreSQL LangGraph Checkpointer。这是明确记录的生产化边界，不能在简历中说成已经完成的能力。

## 自检问题

1. 幂等和乐观锁分别防止什么？
2. 为什么网络调用期间不能持有数据库事务？
3. 为什么模型/工具不可用不应让 API Readiness 直接失败？
4. Fake Adapter 对企业开发有什么价值？
5. 当前组合模式扩成多 Worker 还缺哪几步？
