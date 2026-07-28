# ADR-0005：使用 PostgreSQL 作为权威存储与任务协调基础

> 状态：Proposed
>
> 日期：2026-07-28

## 背景

TripPilot 需要原子行程版本、乐观并发、任务租约、结构化查询、嵌套计划文档、工具缓存和 LangGraph 持久化。当前并发目标较小，引入独立消息队列会增加部署与学习成本。

## 决策

第一版使用 PostgreSQL 18 作为权威数据库，并通过关系列与 JSONB 混合建模。

- SQLAlchemy 2.x Async + psycopg 3 实现数据访问。
- Alembic 管理业务 Schema。
- 任务执行器使用短事务、租约和 `FOR UPDATE SKIP LOCKED` 认领任务。
- LangGraph 使用异步 PostgreSQL Checkpointer。
- 不可变 TripPlan 聚合以版本化 JSONB 保存。
- 不引入 Redis、RabbitMQ 或 Celery 作为第一版必需组件。

## 备选方案

### SQLite

本地启动简单，但并发锁、任务认领和与演示环境一致性不足。可以用于极小单元测试，不作为集成环境权威数据库。

### PostgreSQL + Redis/Celery

任务能力成熟，但增加一个数据系统、队列协议、故障模式和部署单元。当前吞吐没有证明其必要性。

### 文档数据库

适合嵌套计划，但任务租约、行程版本事务、唯一约束和关系查询仍需额外设计。

## 影响与后果

- 本地开发需要 Docker 或可访问的 PostgreSQL。
- 数据库同时承担业务和轻量任务协调，需要监控连接池与轮询负载。
- 网络调用不得在数据库事务中执行。
- JSONB Schema 由应用和版本字段维护，数据库不能替代 Pydantic 校验。
- 达到容量或隔离阈值时可以保留任务端口并迁移到独立队列。
