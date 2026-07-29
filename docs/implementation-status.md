# 实现状态与能力边界

> 版本：Portfolio MVP v0.1
>
> 更新日期：2026-07-29

## 已交付

- 自然语言需求提取、缺失字段补全和用户确认
- LangGraph 有限状态图、并发上下文加载、最多三份候选和确定性约束检查
- Fake Model/Tools 与 OpenAI Responses、Open‑Meteo、高德地点适配器
- FastAPI 异步任务、轮询、取消、结果、保存和删除 API
- 不透明 Token、摘要存储、Idempotency-Key、ETag/If-Match 和稳定错误
- 旅行领域模型、预算/约束服务、SQLAlchemy 模型、Alembic 迁移和 Worker 租约算法
- React 响应式前端
- JSON 日志、敏感字段脱敏和 FastAPI OpenTelemetry Instrumentation
- 单元/集成测试、85% 覆盖率门禁、前后端 CI
- 60 场景版本化评测数据集及契约门禁
- Docker 与 Compose 演示环境

## 已设计但未在 Portfolio MVP 完整交付

这些不是隐藏问题，而是明确的下一阶段 Backlog：

| 能力 | 当前证据 | 完整生产化还需要 |
| --- | --- | --- |
| 多进程持久化任务 | PostgreSQL Schema、迁移、租约查询 | PostgreSQL Coordinator、独立 Worker、持久化 Checkpoint、崩溃恢复测试 |
| 局部修改行程 | API/数据/状态设计、`PlanChange` 模型 | 修改任务执行器、前端交互、版本保持率评测 |
| 全量 60 场景行为 Eval | 版本化场景、契约 Runner、核心离线测试 | Fixture 执行器、真实模型 Workflow、基线报告与人工评分 |
| 路线真实数据进入计划 | RoutePort 与 Fake Route | 高德 Route Adapter、批量调用预算、路线缓存和计划组装 |
| 正式公网部署 | Docker 镜像与 Compose | 托管平台、Secret、域名/TLS、监控告警、备份恢复和压测 |

## 为什么这样划分

Portfolio MVP 的目标是把 Agent 关键知识和企业工程方法形成可以运行、测试和解释的闭环，不用未经验证的代码假装已经达到生产 SLA。面试时可以展示已完成能力，并用架构文档说明下一阶段如何演进。
