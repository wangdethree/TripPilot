# HTTP API 设计

> 状态：Accepted
>
> 基线：v1.0

第一版使用版本化 REST API。创建、确认和修改等命令快速返回任务令牌，客户端通过轮询获取状态；业务正确性不依赖长连接。

## 通用约定

- API 前缀：`/api/v1`
- 请求与响应：`application/json`
- 时间：ISO 8601 UTC 时间戳，旅行本地时间字段按 `Asia/Shanghai`
- 金额：JSON 字符串形式的十进制人民币元，例如 `"1999.50"`
- 标识：服务端内部使用 UUID，外部使用不透明访问令牌
- 错误：稳定错误码、用户可读信息、可操作建议和 `trace_id`
- 写命令：支持 `Idempotency-Key`
- 乐观并发：使用 `ETag` 与 `If-Match`

## 匿名访问令牌

创建任务时返回一次任务访问令牌：

```json
{
  "task_token": "tp_task_<opaque-secret>",
  "status": "COLLECTING_REQUIREMENTS",
  "poll_after_seconds": 1
}
```

保存行程时返回行程访问令牌：

```json
{
  "plan_token": "tp_plan_<opaque-secret>",
  "version": 1,
  "expires_at": "2026-08-27T12:00:00Z"
}
```

后续请求使用：

```http
Authorization: Bearer <opaque-token>
```

服务端只保存令牌摘要。Web 分享链接把令牌放在 URL Fragment 中，由客户端读取后通过 Header 发送；Fragment 不会作为 HTTP 路径或查询参数发送给服务端。

令牌不得出现在普通访问日志、错误响应、Trace 或分析事件中。

## 响应结构

成功响应直接返回资源 DTO，并包含 `trace_id` 响应头。错误统一为：

```json
{
  "error": {
    "code": "VERSION_CONFLICT",
    "message": "行程已经产生新版本，请重新确认修改。",
    "details": {
      "latest_version": 3
    },
    "suggested_actions": [
      "重新加载最新行程"
    ]
  },
  "trace_id": "01J..."
}
```

`details` 只包含允许公开的结构化字段，不包含堆栈、密钥、完整令牌或供应商响应。

## 规划任务 API

### 创建任务

```http
POST /api/v1/planning-tasks
Idempotency-Key: <client-generated-key>
```

```json
{
  "message": "国庆去成都玩三天，两个人，预算三千元，喜欢历史和美食。"
}
```

响应：

- `202 Accepted`
- 返回 `task_token`、初始状态和建议轮询间隔
- 原始输入进入短期处理队列，完成提取后尽快删除

### 追加信息

```http
POST /api/v1/planning-tasks/current/messages
Authorization: Bearer <task-token>
Idempotency-Key: <key>
If-Match: "<request-revision>"
```

```json
{
  "message": "预算不包含住宿，10 月 2 日出发。"
}
```

返回 `202 Accepted`。异步提取完成后，任务状态或需求修订号变化。

### 查询任务

```http
GET /api/v1/planning-tasks/current
Authorization: Bearer <task-token>
```

响应包含：

- `status`
- `workflow_step`
- `request_summary`
- `missing_fields`
- `assumptions`
- `unresolved_constraints`
- `attempt_number`
- `resource_usage`
- `result_available`
- `next_actions`
- `updated_at`

响应头包含：

- `ETag: "<row-version>"`
- `Retry-After: <seconds>`，任务执行中时提供

### 确认需求

```http
POST /api/v1/planning-tasks/current/confirmation
Authorization: Bearer <task-token>
Idempotency-Key: <key>
If-Match: "<request-revision>"
```

```json
{
  "confirmed": true
}
```

只有状态为 `AWAITING_CONFIRMATION` 且修订号匹配时接受，返回 `202 Accepted` 并进入正式规划。

### 取消任务

```http
POST /api/v1/planning-tasks/current/cancellation
Authorization: Bearer <task-token>
Idempotency-Key: <key>
```

返回：

- `202 Accepted`：已持久化取消意图，正在传播
- `200 OK`：任务已经是 `CANCELLED`
- `409 Conflict`：任务已经进入其他结果状态

### 获取结果

```http
GET /api/v1/planning-tasks/current/result
Authorization: Bearer <task-token>
```

- `200 OK`：返回 `COMPLETED` 或 `PARTIAL` TripPlan
- `202 Accepted`：仍在执行
- `409 Conflict`：`NEEDS_USER_INPUT`
- `422 Unprocessable Content`：任务以稳定业务失败结束

失败任务的具体错误仍通过统一错误结构返回。

### 保存结果

```http
POST /api/v1/planning-tasks/current/saved-plan
Authorization: Bearer <task-token>
Idempotency-Key: <key>
```

仅允许保存可展示结果。返回 `201 Created` 和一次性展示的 `plan_token`。

## 行程 API

### 获取最新行程

```http
GET /api/v1/plans/current
Authorization: Bearer <plan-token>
```

返回最新版本、来源时效和保留期限。响应头：

```http
ETag: "\"3\""
```

### 获取版本列表

```http
GET /api/v1/plans/current/versions
Authorization: Bearer <plan-token>
```

只返回版本号、时间、变更摘要和警告，不默认返回所有完整版本。

### 获取指定版本

```http
GET /api/v1/plans/current/versions/{version}
Authorization: Bearer <plan-token>
```

过期来源保留原始查询时间并标记，不显示为最新事实。

### 创建局部修改任务

```http
POST /api/v1/plans/current/modification-tasks
Authorization: Bearer <plan-token>
Idempotency-Key: <key>
If-Match: "\"3\""
```

```json
{
  "change_request": "只把第二天下午改成室内活动，其他日期不变。"
}
```

响应 `202 Accepted`，返回新的 `task_token`。`If-Match` 缺失返回 `428 Precondition Required`；版本不是最新值时返回 `409 VERSION_CONFLICT` 和最新版本号。

### 删除匿名行程

```http
DELETE /api/v1/plans/current
Authorization: Bearer <plan-token>
Idempotency-Key: <key>
```

删除操作对资源状态保持幂等，不会恢复或重复创建数据。首次删除成功后，该令牌立即失效；再次使用时与不存在或过期令牌返回相同外部错误。

## HTTP 状态映射

| HTTP | 使用场景 |
| ---: | --- |
| `200` | 查询成功、已经完成的幂等操作 |
| `201` | 匿名行程保存成功 |
| `202` | 已接受异步命令或任务仍在执行 |
| `400` | JSON 或基础请求格式错误 |
| `401` | 令牌缺失或不可用，外部不区分不存在、过期、删除 |
| `409` | 状态冲突、版本冲突或结果需要用户决策 |
| `422` | 结构合法但违反业务输入规则，或任务业务失败 |
| `428` | 缺少必需的 `If-Match` |
| `429` | 限流或并发任务上限 |
| `500` | 未归类内部错误 |
| `503` | 当前无法接受任务的基础设施故障 |

## 幂等性

- 创建任务、追加消息、确认、取消、保存和修改任务接受 `Idempotency-Key`。
- 键在令牌主体与命令类型范围内唯一。
- 同一键和相同请求返回第一次结果。
- 同一键和不同请求返回 `409 Conflict`。
- 服务端不把原始幂等键写入日志，数据库保存摘要。

## 状态与缓存

- 任务查询使用短轮询，服务端通过 `Retry-After` 建议下一次间隔。
- 客户端使用指数退避和随机抖动，但最长间隔不得让用户明显失去状态反馈。
- 结果状态停止轮询。
- 第一版不依赖 WebSocket。
- SSE 可以作为进度体验增强，但必须复用相同任务状态和查询 API。

## OpenAPI 与兼容性

- FastAPI 生成 OpenAPI 3.1 文档。
- 前端类型由 OpenAPI 生成或在 CI 中进行契约校验。
- 新增可选字段属于兼容变更。
- 删除字段、改变语义或收窄枚举需要新的 API 版本或兼容迁移期。
- API DTO 与领域模型分离，避免外部接口变更直接污染领域对象。

## 安全限制

- 单条自然语言消息设置长度上限。
- 所有列表和嵌套对象设置数量与深度上限。
- CORS 只允许配置的前端来源。
- 访问日志对 Authorization、Idempotency-Key 和令牌形态进行脱敏。
- API 不接受任意回调 URL、工具 URL 或供应商名称。
- 错误响应不返回数据库键、SQL、堆栈或模型原始输出。
