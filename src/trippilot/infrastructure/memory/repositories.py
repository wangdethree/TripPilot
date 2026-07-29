"""Concurrency-safe in-memory repositories for local and test modes."""

import asyncio
from dataclasses import replace

from trippilot.domain.models import PlanningTask, TripPlan


class InMemoryTaskRepository:
    def __init__(self) -> None:
        self._tasks: dict[str, PlanningTask] = {}
        self._token_index: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def add(self, task: PlanningTask, token_hash: str) -> None:
        async with self._lock:
            if task.task_id in self._tasks or token_hash in self._token_index:
                raise ValueError("任务已经存在")
            self._tasks[task.task_id] = task
            self._token_index[token_hash] = task.task_id

    async def get_by_token_hash(self, token_hash: str) -> PlanningTask | None:
        async with self._lock:
            task_id = self._token_index.get(token_hash)
            return self._tasks.get(task_id) if task_id is not None else None

    async def save(self, task: PlanningTask) -> None:
        async with self._lock:
            current = self._tasks.get(task.task_id)
            if current is None:
                raise ValueError("任务不存在")
            if task.row_version <= current.row_version:
                raise ValueError("任务版本冲突")
            self._tasks[task.task_id] = task


class InMemoryPlanRepository:
    def __init__(self) -> None:
        self._plans: dict[str, tuple[TripPlan, ...]] = {}
        self._lock = asyncio.Lock()

    async def save_new(self, plan: TripPlan, token_hash: str) -> TripPlan:
        async with self._lock:
            if token_hash in self._plans:
                raise ValueError("行程令牌已经存在")
            saved = replace(plan, plan_id=f"plan-{len(self._plans) + 1}")
            self._plans[token_hash] = (saved,)
            return saved

    async def get_latest(self, token_hash: str) -> TripPlan | None:
        async with self._lock:
            versions = self._plans.get(token_hash)
            return versions[-1] if versions else None

    async def delete(self, token_hash: str) -> bool:
        async with self._lock:
            return self._plans.pop(token_hash, None) is not None
