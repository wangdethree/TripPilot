from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, date, datetime, time

import pytest

from trippilot.domain.enums import Pace, TaskStatus, WorkflowStep
from trippilot.domain.errors import InvalidStateTransitionError, ValidationError
from trippilot.domain.models import PlanningTask, TravelRequest
from trippilot.domain.value_objects import Money, TravelDateRange


def test_request_exposes_defaults(travel_request: TravelRequest) -> None:
    assert travel_request.days == 1
    assert len(travel_request.explicit_defaults) == 3


@pytest.mark.parametrize(
    "mutate",
    [
        lambda request: replace(request, destination_city=" "),
        lambda request: replace(request, traveler_count=0),
        lambda request: replace(request, budget_total=Money.zero()),
        lambda request: replace(request, interests=()),
        lambda request: replace(request, daily_end_time=time(8)),
        lambda request: replace(request, language="en-US"),
        lambda request: replace(request, timezone="UTC"),
    ],
)
def test_request_rejects_invalid_data(
    travel_request: TravelRequest,
    mutate: Callable[[TravelRequest], TravelRequest],
) -> None:
    with pytest.raises(ValidationError):
        mutate(travel_request)


def test_request_rejects_place_conflict(travel_request: TravelRequest) -> None:
    with pytest.raises(ValidationError):
        replace(travel_request, must_visit=("武侯祠",), avoid_places=("武侯祠",))


def test_task_state_machine_rejects_terminal_rollback() -> None:
    now = datetime(2030, 1, 1, tzinfo=UTC)
    task = PlanningTask(
        task_id="task-1",
        status=TaskStatus.COLLECTING_REQUIREMENTS,
        started_at=now,
    )
    awaiting = task.transition(
        TaskStatus.AWAITING_CONFIRMATION,
        now=now,
        workflow_step=WorkflowStep.AWAIT_CONFIRMATION,
    )
    planning = awaiting.transition(TaskStatus.PLANNING, now=now)
    completed = planning.transition(TaskStatus.COMPLETED, now=now)
    assert completed.finished_at == now
    assert completed.row_version == 4
    with pytest.raises(InvalidStateTransitionError):
        completed.transition(TaskStatus.PLANNING, now=now)


def test_task_cancellation_intent_and_invariants() -> None:
    now = datetime(2030, 1, 1, tzinfo=UTC)
    task = PlanningTask(
        task_id="task-1",
        status=TaskStatus.COLLECTING_REQUIREMENTS,
        started_at=now,
    )
    assert task.request_cancellation().cancel_requested
    with pytest.raises(ValidationError):
        replace(task, attempt_number=4)
    with pytest.raises(ValidationError):
        replace(task, finished_at=now)


def test_travel_request_can_be_constructed_explicitly() -> None:
    request = TravelRequest(
        destination_city="西安",
        date_range=TravelDateRange.from_days(date(2030, 2, 1), 2),
        traveler_count=1,
        budget_total=Money.of("1000"),
        budget_includes_accommodation=True,
        interests=("历史",),
        pace=Pace.RELAXED,
        daily_start_time=time(10),
        daily_end_time=time(18),
    )
    assert request.explicit_defaults == ("交通偏好采用默认值: 公共交通、步行",)
