"""In-process task coordinator used by the local runtime.

The production PostgreSQL executor implements the same lifecycle. This local
coordinator keeps the demo self-contained without hiding cancellation or
terminal-state semantics behind FastAPI background tasks.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from uuid import uuid4

from trippilot.application import PlanningWorkflow, RequirementService, TokenService
from trippilot.application.dto import RequirementDraft, ResourceUsage
from trippilot.domain.enums import ErrorCode, TaskStatus, WorkflowStep
from trippilot.domain.errors import DomainError
from trippilot.domain.models import TravelRequest, TripPlan
from trippilot.infrastructure.memory import InMemoryPlanRepository


@dataclass(slots=True)
class RuntimeTask:
    task_id: str
    status: TaskStatus
    draft: RequirementDraft
    created_at: datetime
    updated_at: datetime
    row_version: int = 1
    workflow_step: WorkflowStep | None = None
    confirmed_request: TravelRequest | None = None
    result: TripPlan | None = None
    usage: ResourceUsage = field(default_factory=ResourceUsage)
    error: DomainError | None = None
    execution: asyncio.Task[None] | None = None


class TaskCoordinator:
    def __init__(
        self,
        *,
        requirements: RequirementService,
        planning: PlanningWorkflow,
        tokens: TokenService,
        plans: InMemoryPlanRepository,
    ) -> None:
        self._requirements = requirements
        self._planning = planning
        self._tokens = tokens
        self._plans = plans
        self._tasks: dict[str, RuntimeTask] = {}
        self._lock = asyncio.Lock()

    async def create(self, message: str) -> tuple[str, RuntimeTask]:
        draft = await self._requirements.collect(message)
        now = datetime.now(UTC)
        status = (
            TaskStatus.COLLECTING_REQUIREMENTS
            if draft.missing_fields or draft.ambiguities
            else TaskStatus.AWAITING_CONFIRMATION
        )
        task = RuntimeTask(
            task_id=str(uuid4()),
            status=status,
            draft=draft,
            workflow_step=(
                WorkflowStep.VALIDATE_REQUEST
                if status is TaskStatus.COLLECTING_REQUIREMENTS
                else WorkflowStep.AWAIT_CONFIRMATION
            ),
            created_at=now,
            updated_at=now,
        )
        token = self._tokens.issue_task_token()
        async with self._lock:
            self._tasks[self._tokens.digest(token)] = task
        return token, task

    async def get(self, token: str) -> RuntimeTask:
        async with self._lock:
            task = self._tasks.get(self._tokens.digest(token))
            if task is None:
                raise _not_available("任务令牌不存在或已经失效")
            return task

    async def add_message(
        self,
        token: str,
        message: str,
        *,
        expected_version: int | None,
    ) -> RuntimeTask:
        task = await self.get(token)
        if task.status not in {
            TaskStatus.COLLECTING_REQUIREMENTS,
            TaskStatus.AWAITING_CONFIRMATION,
        }:
            raise DomainError(
                ErrorCode.VALIDATION_ERROR,
                "当前任务状态不能追加需求",
            )
        self._check_version(task, expected_version)
        draft = await self._requirements.collect(message, existing=task.draft)
        async with self._lock:
            task.draft = draft
            task.status = (
                TaskStatus.COLLECTING_REQUIREMENTS
                if draft.missing_fields or draft.ambiguities
                else TaskStatus.AWAITING_CONFIRMATION
            )
            task.workflow_step = (
                WorkflowStep.VALIDATE_REQUEST
                if task.status is TaskStatus.COLLECTING_REQUIREMENTS
                else WorkflowStep.AWAIT_CONFIRMATION
            )
            self._touch(task)
        return task

    async def confirm(
        self,
        token: str,
        *,
        expected_version: int | None,
        today: date,
    ) -> RuntimeTask:
        task = await self.get(token)
        if task.status is not TaskStatus.AWAITING_CONFIRMATION:
            raise DomainError(
                ErrorCode.CONFIRMATION_REQUIRED,
                "需求尚未完整或任务不在等待确认状态",
                details={"missing_fields": task.draft.missing_fields},
            )
        self._check_version(task, expected_version)
        confirmed = self._requirements.confirm(task.draft, today=today)
        async with self._lock:
            task.confirmed_request = confirmed
            task.status = TaskStatus.PLANNING
            task.workflow_step = WorkflowStep.LOAD_PLANNING_CONTEXT
            self._touch(task)
            task.execution = asyncio.create_task(
                self._execute(task),
                name=f"trippilot-{task.task_id}",
            )
        return task

    async def cancel(self, token: str) -> RuntimeTask:
        task = await self.get(token)
        if task.status.is_terminal:
            if task.status is TaskStatus.CANCELLED:
                return task
            raise DomainError(
                ErrorCode.VALIDATION_ERROR,
                "任务已经进入结果状态, 无法取消",
            )
        if task.execution is not None:
            task.execution.cancel()
        async with self._lock:
            task.status = TaskStatus.CANCELLED
            task.workflow_step = None
            self._touch(task)
        return task

    async def save_result(self, token: str) -> tuple[str, TripPlan]:
        task = await self.get(token)
        if task.result is None or task.status not in {
            TaskStatus.COMPLETED,
            TaskStatus.PARTIAL,
        }:
            raise DomainError(
                ErrorCode.PLAN_NOT_AVAILABLE,
                "当前任务还没有可保存的行程",
            )
        plan_token = self._tokens.issue_plan_token()
        saved = await self._plans.save_new(
            task.result,
            self._tokens.digest(plan_token),
        )
        return plan_token, saved

    async def get_plan(self, token: str) -> TripPlan:
        plan = await self._plans.get_latest(self._tokens.digest(token))
        if plan is None:
            raise _not_available("行程不存在、已过期或已删除")
        return plan

    async def delete_plan(self, token: str) -> None:
        deleted = await self._plans.delete(self._tokens.digest(token))
        if not deleted:
            raise _not_available("行程不存在、已过期或已删除")

    async def close(self) -> None:
        async with self._lock:
            executions = [
                task.execution
                for task in self._tasks.values()
                if task.execution is not None and not task.execution.done()
            ]
        for execution in executions:
            execution.cancel()
        if executions:
            await asyncio.gather(*executions, return_exceptions=True)

    async def _execute(self, task: RuntimeTask) -> None:
        assert task.confirmed_request is not None
        try:
            result, usage = await self._planning.run(task.confirmed_request)
        except asyncio.CancelledError:
            return
        except DomainError as exc:
            async with self._lock:
                task.error = exc
                task.status = (
                    TaskStatus.NEEDS_USER_INPUT
                    if exc.code is ErrorCode.REPLAN_LIMIT_REACHED
                    else TaskStatus.FAILED
                )
                task.workflow_step = None
                self._touch(task)
        except Exception as exc:
            async with self._lock:
                task.error = DomainError(
                    ErrorCode.INTERNAL_ERROR,
                    "规划任务发生未预期错误",
                    details={"exception_type": type(exc).__name__},
                )
                task.status = TaskStatus.FAILED
                task.workflow_step = None
                self._touch(task)
        else:
            async with self._lock:
                if task.status is TaskStatus.CANCELLED:
                    return
                task.result = result
                task.usage = usage
                task.status = result.status
                task.workflow_step = None
                self._touch(task)

    @staticmethod
    def _check_version(task: RuntimeTask, expected_version: int | None) -> None:
        if expected_version is not None and expected_version != task.row_version:
            raise DomainError(
                ErrorCode.VERSION_CONFLICT,
                "任务需求已经产生新版本",
                details={"latest_version": task.row_version},
            )

    @staticmethod
    def _touch(task: RuntimeTask) -> None:
        task.row_version += 1
        task.updated_at = datetime.now(UTC)


def _not_available(message: str) -> DomainError:
    return DomainError(ErrorCode.PLAN_NOT_AVAILABLE, message)
