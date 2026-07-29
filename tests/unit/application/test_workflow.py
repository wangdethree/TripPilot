from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

from trippilot.application import PlanningWorkflow, RequirementService, TokenService
from trippilot.application.dto import PlaceCandidate, RequirementDraft, WeatherDay
from trippilot.domain.enums import ErrorCode, TaskStatus
from trippilot.domain.errors import DomainError
from trippilot.domain.models import PlanningTask, TravelRequest
from trippilot.domain.value_objects import Money, TravelDateRange
from trippilot.infrastructure.fakes import (
    FakePlaceTool,
    FakePlanGenerator,
    FakeRequirementExtractor,
    FakeWeatherTool,
)
from trippilot.infrastructure.memory import InMemoryPlanRepository, InMemoryTaskRepository


@pytest.mark.asyncio
async def test_fake_extractor_collects_and_merges_requirements() -> None:
    service = RequirementService(FakeRequirementExtractor())
    first = await service.collect("2030-10-02 去成都玩三天, 两个人, 预算 3000 元, 喜欢历史和美食")
    assert first.destination_city == "成都"
    assert first.days == 3
    assert first.budget_includes_accommodation is None
    assert first.missing_fields == ("budget_includes_accommodation",)

    merged = await service.collect("预算不包含住宿, 节奏轻松", existing=first)
    confirmed = service.confirm(merged, today=date(2030, 1, 1))
    assert confirmed.budget_includes_accommodation is False
    assert confirmed.days == 3


@pytest.mark.asyncio
async def test_fake_workflow_completes_end_to_end() -> None:
    request = _request()
    workflow = PlanningWorkflow(
        places=FakePlaceTool(),
        weather=FakeWeatherTool(),
        generator=FakePlanGenerator(),
    )
    plan, usage = await workflow.run(request)
    assert plan.status is TaskStatus.COMPLETED
    assert len(plan.days) == 2
    assert usage.tool_calls == 2
    assert usage.model_calls == 1
    assert usage.candidate_count == 1
    assert plan.constraint_results


@pytest.mark.asyncio
async def test_weather_failure_degrades_to_partial() -> None:
    class FailingWeather:
        async def get_forecast(
            self,
            city: str,
            start_date: date,
            end_date: date,
        ) -> tuple[WeatherDay, ...]:
            del city, start_date, end_date
            raise TimeoutError

    workflow = PlanningWorkflow(
        places=FakePlaceTool(),
        weather=FailingWeather(),
        generator=FakePlanGenerator(),
    )
    plan, _ = await workflow.run(_request())
    assert plan.status is TaskStatus.PARTIAL
    assert any(result.constraint_id == "WEATHER_AVAILABILITY" for result in plan.constraint_results)


@pytest.mark.asyncio
async def test_empty_places_is_a_stable_failure() -> None:
    class EmptyPlaces:
        async def search(
            self,
            city: str,
            interests: tuple[str, ...],
        ) -> tuple[PlaceCandidate, ...]:
            del city, interests
            return ()

    workflow = PlanningWorkflow(
        places=EmptyPlaces(),
        weather=FakeWeatherTool(),
        generator=FakePlanGenerator(),
    )
    with pytest.raises(DomainError) as captured:
        await workflow.run(_request())
    assert captured.value.code is ErrorCode.TOOL_NO_RESULT


@pytest.mark.asyncio
async def test_replanning_stops_after_three_candidates() -> None:
    workflow = PlanningWorkflow(
        places=FakePlaceTool(),
        weather=FakeWeatherTool(),
        generator=FakePlanGenerator(),
    )
    impossible = replace(_request(), budget_total=Money.of("1"))
    with pytest.raises(DomainError) as captured:
        await workflow.run(impossible)
    assert captured.value.code is ErrorCode.REPLAN_LIMIT_REACHED
    assert captured.value.details["failed_constraints"] == ["BUDGET_LIMIT"]


@pytest.mark.asyncio
async def test_memory_repositories_and_token_hashing() -> None:
    tokens = TokenService("development-pepper-value")
    token = tokens.issue_task_token()
    assert token.startswith("tp_task_")
    assert tokens.digest(token) != token
    assert tokens.issue_plan_token().startswith("tp_plan_")

    now = datetime(2030, 1, 1, tzinfo=UTC)
    task = PlanningTask(
        task_id="task-1",
        status=TaskStatus.COLLECTING_REQUIREMENTS,
        started_at=now,
    )
    tasks = InMemoryTaskRepository()
    token_hash = tokens.digest(token)
    await tasks.add(task, token_hash)
    assert await tasks.get_by_token_hash(token_hash) == task
    changed = task.transition(TaskStatus.AWAITING_CONFIRMATION, now=now)
    await tasks.save(changed)
    assert await tasks.get_by_token_hash(token_hash) == changed

    workflow = PlanningWorkflow(
        places=FakePlaceTool(),
        weather=FakeWeatherTool(),
        generator=FakePlanGenerator(),
    )
    plan, _ = await workflow.run(_request())
    plans = InMemoryPlanRepository()
    plan_token_hash = tokens.digest(tokens.issue_plan_token())
    saved = await plans.save_new(plan, plan_token_hash)
    assert saved.plan_id is not None
    assert await plans.get_latest(plan_token_hash) == saved
    assert await plans.delete(plan_token_hash)
    assert await plans.get_latest(plan_token_hash) is None


def test_draft_reports_all_required_fields() -> None:
    assert RequirementDraft().missing_fields == (
        "destination_city",
        "start_date",
        "traveler_count",
        "budget_total",
        "budget_includes_accommodation",
        "end_date_or_days",
        "interests",
    )


def test_token_service_rejects_short_pepper() -> None:
    with pytest.raises(ValueError):
        TokenService("short")


def _request() -> TravelRequest:
    return TravelRequest(
        destination_city="成都",
        date_range=TravelDateRange.from_days(date(2030, 10, 2), 2),
        traveler_count=2,
        budget_total=Money.of("3000"),
        budget_includes_accommodation=False,
        interests=("历史", "美食"),
    )
