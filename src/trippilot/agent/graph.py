"""Explicit LangGraph implementation of the TripPilot planning workflow."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import Literal, Required, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

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


class PlanningState(TypedDict, total=False):
    request: Required[TravelRequest]
    context: PlanningContext
    context_unknowns: tuple[ConstraintResult, ...]
    candidate: TripPlan
    results: tuple[ConstraintResult, ...]
    failures: tuple[ConstraintResult, ...]
    attempt: int
    usage: ResourceUsage
    final_plan: TripPlan


PlanningGraph = CompiledStateGraph[
    PlanningState,
    None,
    PlanningState,
    PlanningState,
]


def build_planning_graph(
    *,
    places: PlacePort,
    weather: WeatherPort,
    generator: PlanGeneratorPort,
    max_candidates: int,
) -> PlanningGraph:
    async def load_context(state: PlanningState) -> dict[str, object]:
        request = state["request"]
        place_task = asyncio.create_task(places.search(request.destination_city, request.interests))
        weather_task = asyncio.create_task(
            weather.get_forecast(
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
                    *(weather_day.source for weather_day in weather_days),
                )
            ),
        )
        return {
            "context": context,
            "context_unknowns": tuple(unknowns),
            "usage": ResourceUsage(tool_calls=2),
            "attempt": 0,
            "failures": (),
        }

    async def generate_candidate(state: PlanningState) -> dict[str, object]:
        attempt = state["attempt"] + 1
        candidate = await generator.generate(
            state["request"],
            state["context"],
            attempt=attempt,
            failures=state.get("failures", ()),
        )
        usage = state["usage"]
        return {
            "attempt": attempt,
            "candidate": candidate,
            "usage": replace(
                usage,
                model_calls=usage.model_calls + 1,
                candidate_count=attempt,
            ),
        }

    def validate_candidate(state: PlanningState) -> dict[str, object]:
        results = (
            *validate_plan(state["candidate"]),
            *state.get("context_unknowns", ()),
        )
        failures = tuple(
            result
            for result in results
            if result.severity is ConstraintSeverity.HARD and result.status is CheckStatus.FAIL
        )
        return {"results": results, "failures": failures}

    def route_after_validation(
        state: PlanningState,
    ) -> Literal["finalize", "prepare_replan", "stop"]:
        if not has_hard_failures(state["results"]):
            return "finalize"
        if state["attempt"] >= max_candidates:
            return "stop"
        return "prepare_replan"

    def prepare_replan(state: PlanningState) -> dict[str, object]:
        return {
            "candidate": state["candidate"],
            "failures": state["failures"],
        }

    def finalize(state: PlanningState) -> dict[str, object]:
        status = (
            TaskStatus.PARTIAL if has_important_unknowns(state["results"]) else TaskStatus.COMPLETED
        )
        return {
            "final_plan": replace(
                state["candidate"],
                status=status,
                constraint_results=state["results"],
            )
        }

    def stop(state: PlanningState) -> dict[str, object]:
        raise DomainError(
            ErrorCode.REPLAN_LIMIT_REACHED,
            "三份候选计划仍未通过硬性约束检查",
            details={
                "failed_constraints": [result.constraint_id for result in state["failures"]],
                "closest_candidate_version": state["candidate"].version,
            },
            suggested_actions=("提高预算", "减少必去地点", "调整每日可用时间"),
        )

    graph = StateGraph(PlanningState)
    graph.add_node("load_context", load_context)
    graph.add_node("generate_candidate", generate_candidate)
    graph.add_node("validate_candidate", validate_candidate)
    graph.add_node("prepare_replan", prepare_replan)
    graph.add_node("finalize", finalize)
    graph.add_node("stop", stop)
    graph.add_edge(START, "load_context")
    graph.add_edge("load_context", "generate_candidate")
    graph.add_edge("generate_candidate", "validate_candidate")
    graph.add_conditional_edges(
        "validate_candidate",
        route_after_validation,
        {
            "finalize": "finalize",
            "prepare_replan": "prepare_replan",
            "stop": "stop",
        },
    )
    graph.add_edge("prepare_replan", "generate_candidate")
    graph.add_edge("finalize", END)
    graph.add_edge("stop", END)
    return graph.compile(checkpointer=InMemorySaver())
