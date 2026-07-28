# 架构决策记录

本目录保存 Architecture Decision Records（ADR），用于记录重要技术决策及其背景、备选方案和后果。

文件命名格式：

```text
NNNN-short-title.md
```

每条 ADR 至少包含：

- 状态
- 背景
- 决策
- 备选方案
- 影响与后果

## 决策列表

- [ADR-0001：使用可替换的外部工具适配器](0001-use-replaceable-tool-adapters.md)
- [ADR-0002：服务端采用模块化单体架构](0002-use-modular-monolith.md)
- [ADR-0003：使用显式状态图编排 Agent](0003-use-explicit-agent-workflow.md)
- [ADR-0004：使用 LangGraph 作为工作流运行时](0004-use-langgraph-runtime.md)
- [ADR-0005：使用 PostgreSQL 作为权威存储与任务协调基础](0005-use-postgresql.md)
- [ADR-0006：通过模型端口接入 OpenAI Responses API](0006-use-openai-responses-adapter.md)
- [ADR-0007：长任务采用 REST 命令与状态轮询](0007-use-rest-polling-for-tasks.md)
