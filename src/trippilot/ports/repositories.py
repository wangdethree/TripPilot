"""Persistence ports for tasks, plans and idempotent commands."""

from typing import Protocol

from trippilot.domain.models import PlanningTask, TripPlan


class TaskRepository(Protocol):
    async def add(self, task: PlanningTask, token_hash: str) -> None: ...

    async def get_by_token_hash(self, token_hash: str) -> PlanningTask | None: ...

    async def save(self, task: PlanningTask) -> None: ...


class PlanRepository(Protocol):
    async def save_new(self, plan: TripPlan, token_hash: str) -> TripPlan: ...

    async def get_latest(self, token_hash: str) -> TripPlan | None: ...

    async def delete(self, token_hash: str) -> bool: ...
