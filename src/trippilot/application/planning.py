"""Finite, controlled planning workflow."""

from __future__ import annotations

import asyncio
from dataclasses import replace

from trippilot.application.dto import PlanningContext, ResourceUsage, WeatherDay
from trippilot.domain.enums import (
    CheckStatus,
    ConstraintCategory,
    ConstraintSeverity,
    ErrorCode,
    TaskStatus,
)
from trippilot.domain.errors import DomainError
from trippilot.domain.models import ConstraintResult, TravelRequest, TripPlan
from trippilot.domain.services import (
    has_hard_failures,
    has_important_unknowns,
    validate_plan,
)
from trippilot.ports import PlacePort, PlanGeneratorPort, WeatherPort


class PlanningWorkflow:
    """The workflow owns tool order, retry limits and the final success decision."""

    def __init__(
        self,
        *,
        places: PlacePort,
        weather: WeatherPort,
        generator: PlanGeneratorPort,
        max_candidates: int = 3,
    ) -> None:
        self._places = places
        self._weather = weather
        self._generator = generator
        self._max_candidates = max_candidates

    async def run(self, request: TravelRequest) -> tuple[TripPlan, ResourceUsage]:
        context, usage, context_unknowns = await self._load_context(request)
        previous_failures: tuple[ConstraintResult, ...] = ()
        closest_candidate: TripPlan | None = None
        for attempt in range(1, self._max_candidates + 1):
            candidate = await self._generator.generate(
                request,
                context,
                attempt=attempt,
                failures=previous_failures,
            )
            results = (*validate_plan(candidate), *context_unknowns)
            usage = replace(
                usage,
                model_calls=usage.model_calls + 1,
                candidate_count=attempt,
            )
            if not has_hard_failures(results):
                final_status = (
                    TaskStatus.PARTIAL if has_important_unknowns(results) else TaskStatus.COMPLETED
                )
                return (
                    replace(
                        candidate,
                        status=final_status,
                        constraint_results=results,
                    ),
                    usage,
                )
            closest_candidate = replace(candidate, constraint_results=results)
            previous_failures = tuple(
                result
                for result in results
                if result.severity is ConstraintSeverity.HARD and result.status is CheckStatus.FAIL
            )
        raise DomainError(
            ErrorCode.REPLAN_LIMIT_REACHED,
            "三份候选计划仍未通过硬性约束检查",
            details={
                "failed_constraints": [result.constraint_id for result in previous_failures],
                "closest_candidate_version": (
                    closest_candidate.version if closest_candidate is not None else None
                ),
            },
            suggested_actions=("提高预算", "减少必去地点", "调整每日可用时间"),
        )

    async def _load_context(
        self,
        request: TravelRequest,
    ) -> tuple[PlanningContext, ResourceUsage, tuple[ConstraintResult, ...]]:
        place_task = asyncio.create_task(
            self._places.search(request.destination_city, request.interests)
        )
        weather_task = asyncio.create_task(
            self._weather.get_forecast(
                request.destination_city,
                request.date_range.start,
                request.date_range.end,
            )
        )
        place_result, weather_result = await asyncio.gather(
            place_task,
            weather_task,
            return_exceptions=True,
        )
        if isinstance(place_result, BaseException) or not place_result:
            raise DomainError(
                ErrorCode.TOOL_NO_RESULT,
                "地点服务没有返回可用于规划的候选地点",
                suggested_actions=("稍后重试", "检查目的地城市"),
            )
        unknowns: list[ConstraintResult] = []
        if isinstance(weather_result, BaseException):
            weather_days: tuple[WeatherDay, ...] = ()
            unknowns.append(
                ConstraintResult(
                    constraint_id="WEATHER_AVAILABILITY",
                    category=ConstraintCategory.WEATHER,
                    severity=ConstraintSeverity.HARD,
                    status=CheckStatus.UNKNOWN,
                    message="天气服务暂时不可用, 出发前需要重新确认",
                    evidence={"provider_status": "unavailable"},
                    suggested_actions=("出发前重新查看天气",),
                )
            )
        else:
            weather_days = weather_result
        context = PlanningContext(
            places=place_result,
            weather=weather_days,
            sources=tuple(
                (
                    *(candidate.source for candidate in place_result),
                    *(weather.source for weather in weather_days),
                )
            ),
        )
        return context, ResourceUsage(tool_calls=2), tuple(unknowns)
