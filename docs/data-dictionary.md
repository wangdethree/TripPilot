# 数据字典

> 状态：Accepted
>
> 阶段：Sprint 0

本文件定义业务数据的语义、逻辑类型、必填性、默认值和校验规则。具体编程语言类型和存储类型在技术设计阶段决定。

## TravelRequest

`TravelRequest` 表示经过自然语言提取、补全并等待用户确认的旅行需求。

| 字段 | 逻辑类型 | 必填 | 默认值 | 业务规则 |
| --- | --- | ---: | --- | --- |
| `destination_city` | 字符串 | 是 | 无 | 必须能规范化为受支持的国内城市 |
| `start_date` | 日期 | 是 | 无 | 不得早于当前日期 |
| `end_date` | 日期 | 是 | 无 | 规范化后必填；可以由开始日期和天数推导，不得早于开始日期 |
| `days` | 整数 | 系统计算 | 无 | 规范化后必填；可以由日期推导，开始和结束日期都计入，结果必须为 1～3 |
| `traveler_count` | 整数 | 是 | 无 | 取值范围为 1～8 |
| `budget_total` | 金额 | 是 | 无 | 所有同行者的全程总预算，必须大于 0 |
| `currency` | 枚举 | 否 | `CNY` | 第一版只支持人民币 |
| `budget_includes_accommodation` | 布尔值 | 是 | 无 | 必须明确预算是否包含住宿 |
| `interests` | 字符串列表 | 是 | 无 | 至少包含一个兴趣 |
| `pace` | 枚举 | 否 | `moderate` | `relaxed`、`moderate`、`intensive` |
| `accommodation_area` | 字符串 | 否 | 空 | 未确定时由系统推荐区域并声明假设 |
| `transport_preferences` | 枚举列表 | 否 | `public_transit`、`walking` | 可包含公共交通、步行、出租车等 |
| `must_visit` | 地点列表 | 否 | 空列表 | 用户确认后成为硬性约束 |
| `avoid_places` | 地点列表 | 否 | 空列表 | 用户确认后成为硬性约束 |
| `dietary_restrictions` | 字符串列表 | 否 | 空列表 | 未提供时不得假设存在限制 |
| `mobility_constraints` | 字符串列表 | 否 | 空列表 | 提供后成为硬性约束 |
| `daily_start_time` | 时间 | 否 | `09:00` | 每日最早安排时间 |
| `daily_end_time` | 时间 | 否 | `21:00` | 必须晚于开始时间 |
| `special_requirements` | 字符串列表 | 否 | 空列表 | 老人、儿童或其他特殊需求 |
| `language` | 枚举 | 否 | `zh-CN` | 第一版只提供简体中文 |
| `timezone` | 时区 | 否 | `Asia/Shanghai` | 第一版固定使用中国标准时间 |

### 金额规则

- 业务单位为人民币元。
- 展示精度保留到分。
- 预算比较必须采用十进制定点规则。
- 具体使用十进制类型还是整数分存储，由技术设计决定。

### 日期规则

- 支持当天或未来的旅行。
- 不支持已经过去的开始日期。
- 用户输入开始日期与天数时，系统推导结束日期；输入开始与结束日期时，系统推导天数。
- 用户同时输入结束日期与天数但两者不一致时，必须请求确认。
- 按自然日计算，开始和结束日期都包含。
- 超出天气服务预测范围时，需求仍然有效，但天气信息标记为 `UNKNOWN`。

## 枚举

### Pace

| 值 | 含义 |
| --- | --- |
| `relaxed` | 轻松节奏，每天最多 3 个主要活动 |
| `moderate` | 适中节奏，每天最多 4 个主要活动 |
| `intensive` | 紧凑节奏，每天最多 5 个主要活动 |

### TaskStatus

| 值 | 含义 |
| --- | --- |
| `COLLECTING_REQUIREMENTS` | 正在收集和补全需求 |
| `AWAITING_CONFIRMATION` | 等待用户确认需求摘要 |
| `PLANNING` | 正在生成初始计划 |
| `REPLANNING` | 正在自动重新规划 |
| `COMPLETED` | 已知硬性约束全部通过 |
| `PARTIAL` | 已生成计划，但存在重要未知信息 |
| `NEEDS_USER_INPUT` | 硬性约束冲突，需要用户决策 |
| `FAILED` | 无法生成可用计划 |
| `CANCELLED` | 用户取消任务 |

### CheckStatus

| 值 | 含义 |
| --- | --- |
| `PASS` | 满足约束 |
| `WARNING` | 存在软性问题，计划仍可使用 |
| `FAIL` | 违反硬性约束 |
| `UNKNOWN` | 缺少可靠信息 |

### TimelineItemType

| 值 | 含义 |
| --- | --- |
| `ACTIVITY` | 景点、参观或体验 |
| `TRANSIT` | 地点之间的交通 |
| `MEAL` | 用餐 |
| `REST` | 休息或自由活动 |

### CostConfidence

| 值 | 含义 |
| --- | --- |
| `KNOWN` | 来自可靠来源的明确费用 |
| `ESTIMATED` | 根据区间、经验或规则估算的费用 |
| `UNKNOWN` | 当前无法可靠确定费用 |

## PlaceRef

`PlaceRef` 表示标准化地点引用。

| 字段 | 逻辑类型 | 必填 | 说明 |
| --- | --- | ---: | --- |
| `place_id` | 字符串 | 是 | 系统内部或外部地点服务的稳定标识 |
| `name` | 字符串 | 是 | 地点展示名称 |
| `address` | 字符串 | 否 | 可核实的地址 |
| `latitude` | 十进制数 | 否 | 纬度 |
| `longitude` | 十进制数 | 否 | 经度 |
| `source_ids` | 标识列表 | 是 | 支撑地点信息的来源 |

坐标缺失时可以展示地点，但依赖坐标的路线或地图能力必须标记为不可用。

## CostEstimate

`CostEstimate` 表示单项费用及其确定程度。

| 字段 | 逻辑类型 | 必填 | 说明 |
| --- | --- | ---: | --- |
| `amount` | 金额或空 | 条件必填 | `UNKNOWN` 时必须为空，其他状态必须有值 |
| `currency` | 枚举 | 是 | 第一版固定为 `CNY` |
| `confidence` | `CostConfidence` | 是 | 已知、估算或未知 |
| `covers_travelers` | 整数 | 是 | 该金额覆盖的同行人数 |
| `description` | 字符串 | 是 | 费用用途 |
| `source_ids` | 标识列表 | 否 | 费用来源 |

未知费用的 `amount` 不得写为 0。

## TripPlan

`TripPlan` 表示一份经过约束检查的行程版本。

| 字段 | 逻辑类型 | 必填 | 说明 |
| --- | --- | ---: | --- |
| `plan_id` | 不可预测标识或空 | 条件必填 | 成功保存后生成，未保存时为空 |
| `version` | 正整数 | 是 | 初始版本为 1，成功修改后递增 |
| `request_snapshot` | `TravelRequest` | 是 | 生成当前版本时使用的已确认需求快照 |
| `status` | `TaskStatus` | 是 | 最终可展示计划只允许 `COMPLETED` 或 `PARTIAL` |
| `days` | `DayPlan` 列表 | 是 | 数量必须与旅行天数一致 |
| `budget_summary` | `BudgetSummary` | 是 | 行程预算汇总 |
| `constraint_results` | `ConstraintResult` 列表 | 是 | 本版本完整检查结果 |
| `assumptions` | 字符串列表 | 是 | 默认值和明确假设 |
| `sources` | `SourceRecord` 列表 | 是 | 动态信息来源 |
| `change_history` | `PlanChange` 列表 | 是 | 从上一版本到当前版本的变更 |
| `generated_at` | 时间戳 | 是 | 首次生成时间 |
| `updated_at` | 时间戳 | 是 | 当前版本生成时间 |

## DayPlan

| 字段 | 逻辑类型 | 必填 | 说明 |
| --- | --- | ---: | --- |
| `date` | 日期 | 是 | 必须位于旅行日期范围内 |
| `theme` | 字符串 | 是 | 当日主题 |
| `timeline_items` | `TimelineItem` 列表 | 是 | 按开始时间升序排列 |
| `daily_budget` | `BudgetSummary` | 是 | 当日预算汇总 |
| `daily_warnings` | 字符串列表 | 是 | 当日软性问题或未知信息 |

## TimelineItem

交通、用餐和休息都作为独立时间线项目，不附着在前后活动的描述中。

| 字段 | 逻辑类型 | 必填 | 说明 |
| --- | --- | ---: | --- |
| `item_id` | 标识 | 是 | 当前行程版本内唯一 |
| `item_type` | `TimelineItemType` | 是 | 活动、交通、用餐或休息 |
| `start_time` | 时间 | 是 | 开始时间 |
| `end_time` | 时间 | 是 | 必须晚于开始时间 |
| `title` | 字符串 | 是 | 用户可读标题 |
| `location` | `PlaceRef` 或空 | 条件必填 | 休息项目可以没有具体地点 |
| `description` | 字符串 | 是 | 安排说明 |
| `reason` | 字符串 | 是 | 推荐或安排原因 |
| `estimated_cost` | `CostEstimate` | 是 | 单项预计费用 |
| `source_ids` | 标识列表 | 是 | 关联来源 |
| `warnings` | 字符串列表 | 是 | 当前项目的警告 |
| `details` | 类型专属对象 | 是 | 根据 `item_type` 使用对应详情 |

同一天的时间线项目不得重叠，且交通与用餐时间必须显式计入日程。

### ActivityDetails

| 字段 | 逻辑类型 | 必填 | 说明 |
| --- | --- | ---: | --- |
| `duration_minutes` | 正整数 | 是 | 停留时间，必须等于条目结束与开始时间之差 |
| `environment` | 枚举 | 是 | `INDOOR`、`OUTDOOR` 或 `MIXED` |
| `reservation_required` | 布尔值或未知 | 是 | 无可靠信息时标记未知 |
| `opening_hours_status` | `CheckStatus` | 是 | 当前安排是否符合开放时间 |
| `interest_tags` | 字符串列表 | 是 | 与用户兴趣匹配的标签 |

### TransitDetails

| 字段 | 逻辑类型 | 必填 | 说明 |
| --- | --- | ---: | --- |
| `origin` | `PlaceRef` | 是 | 出发地点 |
| `destination` | `PlaceRef` | 是 | 到达地点 |
| `transport_mode` | 枚举 | 是 | 步行、公共交通、出租车等 |
| `duration_minutes` | 正整数或空 | 条件必填 | 路线未知时为空 |
| `distance_meters` | 非负整数或空 | 否 | 路线服务提供时记录 |

### MealDetails

| 字段 | 逻辑类型 | 必填 | 说明 |
| --- | --- | ---: | --- |
| `cuisine_types` | 字符串列表 | 是 | 推荐餐饮类型 |
| `estimated_cost_per_person` | `CostEstimate` | 是 | 人均费用 |
| `specific_restaurant_verified` | 布尔值 | 是 | 是否核实了具体餐厅 |

未核实具体餐厅时，不得提供伪造的营业时间、预订状态或确定性地址。

### RestDetails

| 字段 | 逻辑类型 | 必填 | 说明 |
| --- | --- | ---: | --- |
| `flexible` | 布尔值 | 是 | 是否允许在不违反硬性约束时移动或缩短 |
| `minimum_duration_minutes` | 非负整数 | 是 | 可调整时仍应保留的最短休息时间 |

## BudgetSummary

| 字段 | 逻辑类型 | 必填 | 说明 |
| --- | --- | ---: | --- |
| `accommodation` | 金额汇总 | 是 | 住宿 |
| `transportation` | 金额汇总 | 是 | 市内交通 |
| `tickets` | 金额汇总 | 是 | 门票和活动 |
| `meals` | 金额汇总 | 是 | 餐饮 |
| `other` | 金额汇总 | 是 | 其他 |
| `reserve` | 金额 | 是 | 未分配预留金额 |
| `known_total` | 金额 | 是 | 所有旅行类别的 `KNOWN` 费用合计 |
| `estimated_total` | 金额 | 是 | 所有旅行类别的 `ESTIMATED` 费用合计 |
| `budget_scope_total` | 金额 | 是 | 参与用户预算上限判断的已知与估算费用合计 |
| `unknown_items` | `CostEstimate` 列表 | 是 | `UNKNOWN` 费用，不计入数值总和 |
| `remaining_budget` | 金额 | 是 | `budget_total` 减去 `budget_scope_total` |

预算汇总必须区分已知、估算和未知费用。任何未知费用不得以 0 参与合计。`budget_includes_accommodation` 为 `false` 时，住宿仍进入分类汇总、`known_total` 或 `estimated_total`，但不进入 `budget_scope_total`。

## ConstraintResult

| 字段 | 逻辑类型 | 必填 | 说明 |
| --- | --- | ---: | --- |
| `constraint_id` | 字符串 | 是 | 稳定的约束标识 |
| `category` | 枚举 | 是 | 预算、时间、路线、天气等 |
| `severity` | 枚举 | 是 | `HARD` 或 `SOFT` |
| `status` | `CheckStatus` | 是 | 检查结果 |
| `message` | 字符串 | 是 | 用户可读说明 |
| `evidence` | 键值对象 | 是 | 支撑检查结论的结构化证据 |
| `affected_item_ids` | 标识列表 | 是 | 受影响时间线项目 |
| `suggested_actions` | 字符串列表 | 是 | 可选择的修复建议 |

## SourceRecord

| 字段 | 逻辑类型 | 必填 | 说明 |
| --- | --- | ---: | --- |
| `source_id` | 标识 | 是 | 当前计划内唯一 |
| `provider` | 字符串 | 是 | 数据服务商或来源名称 |
| `title` | 字符串 | 是 | 来源标题或查询说明 |
| `url` | URL 或空 | 否 | 存在公开页面时记录 |
| `retrieved_at` | 时间戳 | 是 | 查询时间 |
| `information_type` | 枚举 | 是 | 天气、地点、路线、价格、开放时间等 |
| `related_item_ids` | 标识列表 | 是 | 该来源支撑的时间线项目 |
| `freshness_status` | 枚举 | 是 | `FRESH`、`STALE` 或 `UNKNOWN` |

## PlanChange

| 字段 | 逻辑类型 | 必填 | 说明 |
| --- | --- | ---: | --- |
| `from_version` | 正整数 | 是 | 修改前版本 |
| `to_version` | 正整数 | 是 | 修改后版本，必须等于前一版本加 1 |
| `requested_change` | 字符串 | 是 | 用户提出的修改 |
| `target_dates` | 日期列表 | 是 | 用户指定的修改日期 |
| `target_item_ids` | 标识列表 | 是 | 用户指定的项目 |
| `change_summary` | 字符串列表 | 是 | 实际发生的修改 |
| `preserved_dates` | 日期列表 | 是 | 未被改变的日期 |
| `changed_at` | 时间戳 | 是 | 修改时间 |

## PlanningTask

| 字段 | 逻辑类型 | 必填 | 说明 |
| --- | --- | ---: | --- |
| `task_id` | 标识 | 是 | 单次规划任务唯一标识 |
| `status` | `TaskStatus` | 是 | 当前任务状态 |
| `request_draft` | 部分 `TravelRequest` | 是 | 收集阶段的需求草稿，允许缺少尚未提供的字段 |
| `confirmed_request` | `TravelRequest` 或空 | 条件必填 | 用户确认摘要后必填；确认前为空 |
| `parent_task_id` | 标识或空 | 否 | 因需求调整或继续修改而创建新任务时指向原任务 |
| `attempt_number` | 整数 | 是 | 当前完整候选计划次数，范围为 0～3 |
| `unresolved_constraints` | `ConstraintResult` 列表 | 是 | 尚未解决的约束 |
| `started_at` | 时间戳 | 是 | 任务开始时间 |
| `finished_at` | 时间戳或空 | 否 | 进入终态后记录 |
| `error_code` | 字符串或空 | 否 | 失败时的稳定错误码 |
| `error_message` | 字符串或空 | 否 | 用户可读错误信息 |

## 稳定错误码

| 错误码 | 含义 |
| --- | --- |
| `VALIDATION_ERROR` | 输入字段格式或取值不合法 |
| `UNSUPPORTED_SCOPE` | 请求超出第一版支持范围 |
| `CONFIRMATION_REQUIRED` | 尚未获得首次规划确认 |
| `TOOL_TIMEOUT` | 外部工具达到超时上限 |
| `TOOL_NO_RESULT` | 关键工具没有返回可用结果 |
| `MODEL_UNAVAILABLE` | 大模型服务不可用 |
| `PLAN_VALIDATION_FAILED` | 候选计划无法通过 Schema 或确定性校验 |
| `REPLAN_LIMIT_REACHED` | 自动重规划达到上限 |
| `COST_LIMIT_EXCEEDED` | 模型或工具资源配额达到上限 |
| `RATE_LIMITED` | 客户端超过任务频率或并发限制 |
| `TASK_CANCELLED` | 用户取消任务 |
| `PLAN_NOT_AVAILABLE` | 匿名行程不存在、已过期或已删除 |
| `VERSION_CONFLICT` | 修改所基于的行程版本不是最新版本 |
| `PERSISTENCE_FAILED` | 保存或版本写入失败 |
| `INTERNAL_ERROR` | 无法归类的内部错误 |

错误响应可以包含用户可操作建议，但不得包含堆栈、密钥、完整行程 ID 或敏感数据。
