# 02：Agent 核心

## [必须掌握] Agent 不等于一次大模型调用

在 TripPilot 中，Agent 是一个有目标、有状态、能调用外部能力、会根据反馈调整、并且能终止的系统。LLM 只负责适合概率推理的部分：

- 从自然语言提取结构化需求；
- 在已验证候选地点中选择和组合；
- 根据约束失败反馈生成下一份候选。

金额计算、时间重叠、预算上限、循环次数和状态迁移由普通代码控制。这样才能测试和解释。

## [必须掌握] 状态、节点与边

`PlanningState` 保存图执行所需的数据：

- 已确认 `request`
- 地点、天气与来源 `context`
- 当前 `candidate`
- 约束 `results` 与硬失败 `failures`
- `attempt` 和资源用量 `usage`
- 最终 `final_plan`

节点只完成一个明确动作；条件边根据可检查状态决定下一步。TripPilot 最多生成三份候选，因此不存在无限 ReAct 循环。

## [必须掌握] 结构化输出

模型输出不能直接拼成最终 JSON：

1. Responses API 按 Pydantic Schema 解析；
2. 地点选择只能引用工具返回的 `place_id`；
3. 适配器把选择结果组装成领域对象；
4. 领域对象再次检查不变量；
5. 约束服务独立验证最终计划。

结构化输出解决“格式可解析”，不能自动解决“事实正确”和“业务正确”。后两者仍需要来源限制与确定性检查。

## [必须掌握] 工具调用边界

工具结果被视为不可信数据。Agent 不能：

- 根据地点描述中的指令改变系统规则；
- 调用未注册工具；
- 请求用户提供的任意 URL；
- 在工具失败后让模型虚构天气、路线或价格。

真实适配器固定 Base URL、校验响应、限制超时和重试，并把 `provider`、`retrieved_at`、`freshness_status` 放入来源。

## [应该理解] 为什么不用完全自由的 ReAct

旅行规划有硬边界：确认前不应消耗正式资源、预算不能算错、工具不能越权、重规划必须停止。自由循环提高灵活性，但更难保证成本、状态恢复和安全。TripPilot 采用“工作流控制权限与终止，模型负责局部决策”的受控 Agent。

## [应该理解] 模型分工

- 需求提取使用低延迟模型；
- 规划使用更强推理模型；
- Fake Model 让单测和演示不依赖网络；
- 切换模型必须重新运行评测，不能只看一次主观效果。

## [拓展了解] Checkpoint

当前本地组合模式使用 LangGraph 内存 Checkpoint；架构和 PostgreSQL Schema 为多进程恢复预留了边界。生产级恢复还需要把任务租约、业务状态和 LangGraph Checkpoint 放在同一套故障语义下。

## 动手练习

1. 把 `max_candidates` 从 3 改为 2，观察失败测试。
2. 让天气工具抛出异常，确认结果是 `PARTIAL` 而不是编造天气。
3. 让地点工具返回空列表，确认任务失败。
4. 在 Fake 计划中制造超预算候选，跟踪重新规划路径。

## 自检问题

1. TripPilot 中哪些工作适合 LLM，哪些必须用普通代码？
2. Schema 校验通过为什么不等于行程可靠？
3. `COMPLETED`、`PARTIAL`、`NEEDS_USER_INPUT`、`FAILED` 如何区分？
4. 为什么工具失败后不能让模型“凭经验补一个结果”？
5. 如何证明 Agent 一定终止？

## 官方资料

- [OpenAI Responses API 文本生成](https://developers.openai.com/api/docs/guides/text?api-mode=responses)
- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [OpenAI Function Calling](https://developers.openai.com/api/docs/guides/function-calling)
- [OpenAI 模型选择](https://developers.openai.com/api/docs/guides/latest-model)
- [Open‑Meteo Forecast API](https://open-meteo.com/en/docs)
- [高德 Web 服务地点检索](https://lbs.amap.com/api/webservice/guide/api/search/)
