# 03：项目中的 asyncio

## [必须掌握] 异步解决什么问题

`asyncio` 主要提高 I/O 等待期间的并发利用率，不会让 CPU 计算自动变快。调用模型、天气和地点服务时，程序大部分时间在等网络，因此适合异步。

```python
place_task = asyncio.create_task(places.search(...))
weather_task = asyncio.create_task(weather.get_forecast(...))
place_result, weather_result = await asyncio.gather(
    place_task,
    weather_task,
    return_exceptions=True,
)
```

地点与天气互不依赖，可以并发；候选生成依赖两者结果，必须之后执行。

## [必须掌握] 协程、Task、await

- 调用 `async def` 得到协程对象，还没有完成工作。
- `await` 暂停当前协程并把控制权交还事件循环。
- `create_task` 把协程调度为可并发推进的 Task。
- 丢失 Task 引用会让生命周期和异常难以管理。

## [必须掌握] 取消传播

`TaskCoordinator.confirm` 保存执行 Task；取消命令调用 `task.execution.cancel()`。被取消的协程会在下一个可取消等待点收到 `CancelledError`。

正确做法：

- 不把 `CancelledError` 当普通失败吞掉；
- 清理资源后继续传播，或像 Coordinator 一样明确映射为业务取消；
- 应用关闭时取消未完成任务并 `gather(..., return_exceptions=True)`；
- 写测试确认取消后状态不会又变为 `COMPLETED`。

## [必须掌握] 超时与有限重试

超时属于可靠性边界，不是越长越好。真实工具：

- 单次有明确 timeout；
- 只重试超时、429、5xx 等暂时故障；
- 400、鉴权错误和确定性无结果不盲目重试；
- 重试次数有上限；
- 最终转换为稳定领域错误。

## [应该理解] gather 与 TaskGroup

`gather(return_exceptions=True)` 适合 TripPilot 当前“地点失败致命、天气失败可降级”的结果分类。`TaskGroup` 提供结构化并发：子任务异常时会取消同组其他任务，适合“任意一步失败则整组失败”的场景。

## [应该理解] 并发安全

异步不是没有竞争。两个协程可能在 `await` 之间交错：

- In-memory 仓储和幂等 Store 用 `asyncio.Lock` 保护复合操作；
- PostgreSQL 使用事务、乐观版本和 `FOR UPDATE SKIP LOCKED`；
- 不应让多个并发任务共享同一个 SQLAlchemy `AsyncSession`；
- 网络调用期间不能持有数据库行锁。

## 练习顺序

1. 写两个 `asyncio.sleep` 协程，对比串行和并发耗时。
2. 给一个协程加 `asyncio.timeout`。
3. 创建任务后取消，断言清理逻辑被执行。
4. 阅读 `load_context`，解释为什么天气异常可被保留为 `UNKNOWN`。
5. 阅读 Coordinator 的 `close`，解释为什么需要等待所有取消完成。

## 自检问题

1. `async def` 被调用后是否立即执行？
2. 什么时候用 `await`，什么时候用 `create_task`？
3. 为什么不能对参数错误做两次重试？
4. 取消任务与任务执行完成同时发生时，如何避免终态回退？
5. `asyncio.Lock` 能否保护多个进程？
