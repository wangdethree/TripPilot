# ADR-0006：通过模型端口接入 OpenAI Responses API

> 状态：Proposed
>
> 日期：2026-07-28

## 背景

TripPilot 需要结构化需求提取、候选计划生成和有限重规划，同时要求模型可替换、成本可控、结果可验证。模型 API 和具体模型会持续演进，领域与工作流不能依赖供应商类型。

## 决策

第一版真实模型适配器使用 OpenAI Python SDK 和 Responses API，并实现项目自有 `ModelPort`。

- 需求和计划输出使用 Pydantic Schema 与 Structured Outputs。
- 模型名称、推理强度和供应商参数通过配置提供。
- 开发和自动测试默认使用 Fake Model。
- 工作流只依赖 `ModelPort` DTO，不直接导入 OpenAI SDK 类型。
- 默认由 TripPilot 管理状态并设置 `store: false`。
- 发布评测记录请求模型、实际模型、Prompt、Schema、Token、延迟和成本。
- OpenAI 不可用时返回结构化错误，不自动切换到未评测供应商。

## 备选方案

### Chat Completions API

仍可用于部分模型，但 Responses API 是当前面向推理和工具工作流的推荐接口。

### OpenAI Agents SDK

提供更高层 Agent 能力，但会和 LangGraph 的状态、工具与 Trace 职责重叠。

### 直接依赖 LangChain 模型类

接入方便，但会让模型调用 DTO 和重试语义扩散到工作流。自有端口能保持供应商边界清晰。

### 本地开源模型

可以降低供应商依赖，但本地硬件、部署和中文规划质量需要单独评测。保留为未来适配器，不进入第一版交付关键路径。

## 影响与后果

- 真实集成需要 API Key、网络、配额和费用。
- 结构化输出仍可能拒绝、截断或失败，必须处理所有分支。
- 当前模型别名可能变化，发布候选必须记录实际解析版本并回归。
- 更换模型供应商只需实现端口，但仍必须重新运行完整 Agent 评测。
