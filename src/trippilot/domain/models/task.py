"""Planning task state machine."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from trippilot.domain.enums import TaskStatus, WorkflowStep
from trippilot.domain.errors import InvalidStateTransitionError, ValidationError
from trippilot.domain.models.plan import ConstraintResult, TripPlan
from trippilot.domain.models.request import TravelRequest

_ALLOWED_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.COLLECTING_REQUIREMENTS: frozenset(
        {
            TaskStatus.AWAITING_CONFIRMATION,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        }
    ),
    TaskStatus.AWAITING_CONFIRMATION: frozenset(
        {
            TaskStatus.COLLECTING_REQUIREMENTS,
            TaskStatus.PLANNING,
            TaskStatus.CANCELLED,
        }
    ),
    TaskStatus.PLANNING: frozenset(
        {
            TaskStatus.REPLANNING,
            TaskStatus.COMPLETED,
            TaskStatus.PARTIAL,
            TaskStatus.NEEDS_USER_INPUT,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        }
    ),
    TaskStatus.REPLANNING: frozenset(
        {
            TaskStatus.REPLANNING,
            TaskStatus.COMPLETED,
            TaskStatus.PARTIAL,
            TaskStatus.NEEDS_USER_INPUT,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        }
    ),
}


@dataclass(frozen=True, slots=True)
class PlanningTask:
    task_id: str
    status: TaskStatus
    started_at: datetime
    row_version: int = 1
    workflow_step: WorkflowStep | None = None
    request_draft: TravelRequest | None = None
    confirmed_request: TravelRequest | None = None
    parent_task_id: str | None = None
    attempt_number: int = 0
    unresolved_constraints: tuple[ConstraintResult, ...] = ()
    finished_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None
    result: TripPlan | None = None
    cancel_requested: bool = False

    def __post_init__(self) -> None:
        if not 0 <= self.attempt_number <= 3:
            raise ValidationError("候选计划次数必须为 0-3", field="attempt_number")
        if self.status.is_terminal != (self.finished_at is not None):
            raise ValidationError("任务终态与结束时间不一致", field="finished_at")

    def transition(
        self,
        target: TaskStatus,
        *,
        now: datetime,
        workflow_step: WorkflowStep | None = None,
    ) -> PlanningTask:
        if target not in _ALLOWED_TRANSITIONS.get(self.status, frozenset()):
            raise InvalidStateTransitionError(self.status, target)
        return replace(
            self,
            status=target,
            workflow_step=workflow_step,
            finished_at=now if target.is_terminal else None,
            row_version=self.row_version + 1,
        )

    def request_cancellation(self) -> PlanningTask:
        if self.status.is_terminal:
            raise InvalidStateTransitionError(self.status, TaskStatus.CANCELLED)
        return replace(
            self,
            cancel_requested=True,
            row_version=self.row_version + 1,
        )
