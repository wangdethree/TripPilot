"""OpenAI Responses API adapters.

The model only extracts fields or selects verified place IDs. Domain objects,
budgets, timelines and final success are still built and checked locally.
"""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from datetime import date

from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict, Field

from trippilot.application.dto import PlanningContext, RequirementDraft
from trippilot.domain.enums import ErrorCode, Pace, TransportMode
from trippilot.domain.errors import DomainError
from trippilot.domain.models import ConstraintResult, TravelRequest, TripPlan
from trippilot.domain.value_objects import Money
from trippilot.infrastructure.fakes import FakePlanGenerator

_EXTRACTION_PROMPT_VERSION = "requirement-extraction-v1"
_PLANNING_PROMPT_VERSION = "place-selection-v1"


class RequirementExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    destination_city: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    days: int | None = Field(default=None, ge=1, le=3)
    traveler_count: int | None = Field(default=None, ge=1, le=8)
    budget_total: str | None = None
    budget_includes_accommodation: bool | None = None
    interests: list[str] = Field(default_factory=list, max_length=10)
    pace: Pace | None = None
    transport_preferences: list[TransportMode] = Field(default_factory=list)
    must_visit: list[str] = Field(default_factory=list, max_length=10)
    avoid_places: list[str] = Field(default_factory=list, max_length=10)
    dietary_restrictions: list[str] = Field(default_factory=list, max_length=10)
    mobility_constraints: list[str] = Field(default_factory=list, max_length=10)
    ambiguities: list[str] = Field(default_factory=list, max_length=10)


class PlanSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected_place_ids: list[str] = Field(min_length=1, max_length=6)
    selection_summary: str = Field(min_length=1, max_length=300)


class OpenAIRequirementExtractor:
    def __init__(
        self,
        client: AsyncOpenAI,
        *,
        model: str = "gpt-5.6-luna",
    ) -> None:
        self._client = client
        self._model = model

    async def extract(
        self,
        message: str,
        *,
        existing: RequirementDraft | None = None,
    ) -> RequirementDraft:
        existing_json = json.dumps(
            asdict(existing) if existing is not None else {},
            ensure_ascii=False,
            default=str,
        )
        response = await self._client.responses.parse(
            model=self._model,
            reasoning={"effort": "low"},
            store=False,
            instructions=(
                "你是旅行需求提取器。只提取用户明确提供或可直接推导的信息。"
                "不得猜测缺失的必填字段。新消息要与已有草稿合并, 冲突内容记录在 ambiguities。"
                f"Prompt 版本: {_EXTRACTION_PROMPT_VERSION}"
            ),
            input=f"已有草稿:\n{existing_json}\n\n用户新消息:\n{message}",
            text_format=RequirementExtraction,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise DomainError(
                ErrorCode.PLAN_VALIDATION_FAILED,
                "模型没有返回可解析的需求结构",
            )
        draft = existing or RequirementDraft()
        return replace(
            draft,
            destination_city=parsed.destination_city or draft.destination_city,
            start_date=parsed.start_date or draft.start_date,
            end_date=parsed.end_date or draft.end_date,
            days=parsed.days or draft.days,
            traveler_count=parsed.traveler_count or draft.traveler_count,
            budget_total=(
                Money.of(parsed.budget_total)
                if parsed.budget_total is not None
                else draft.budget_total
            ),
            budget_includes_accommodation=(
                parsed.budget_includes_accommodation
                if parsed.budget_includes_accommodation is not None
                else draft.budget_includes_accommodation
            ),
            interests=_merge(draft.interests, tuple(parsed.interests)),
            pace=parsed.pace or draft.pace,
            transport_preferences=(
                tuple(parsed.transport_preferences)
                if parsed.transport_preferences
                else draft.transport_preferences
            ),
            must_visit=_merge(draft.must_visit, tuple(parsed.must_visit)),
            avoid_places=_merge(draft.avoid_places, tuple(parsed.avoid_places)),
            dietary_restrictions=_merge(
                draft.dietary_restrictions,
                tuple(parsed.dietary_restrictions),
            ),
            mobility_constraints=_merge(
                draft.mobility_constraints,
                tuple(parsed.mobility_constraints),
            ),
            ambiguities=_merge(draft.ambiguities, tuple(parsed.ambiguities)),
        )


class OpenAIPlanGenerator:
    def __init__(
        self,
        client: AsyncOpenAI,
        *,
        model: str = "gpt-5.6-terra",
    ) -> None:
        self._client = client
        self._model = model
        self._assembler = FakePlanGenerator()

    async def generate(
        self,
        request: TravelRequest,
        context: PlanningContext,
        *,
        attempt: int,
        failures: tuple[ConstraintResult, ...] = (),
    ) -> TripPlan:
        candidates = [
            {
                "place_id": candidate.place.place_id,
                "name": candidate.place.name,
                "interest_tags": candidate.interest_tags,
                "indoor": candidate.indoor,
                "ticket_cost_per_person": str(candidate.ticket_cost),
                "description": candidate.description,
            }
            for candidate in context.places
        ]
        response = await self._client.responses.parse(
            model=self._model,
            reasoning={"effort": "medium"},
            store=False,
            instructions=(
                "你是国内城市短途旅行规划器。只能从候选地点中选择 place_id, "
                "不得创建地点、价格或来源。优先满足硬约束和兴趣, 同时控制预算与路线。"
                f"Prompt 版本: {_PLANNING_PROMPT_VERSION}"
            ),
            input=json.dumps(
                {
                    "request": {
                        "city": request.destination_city,
                        "days": request.days,
                        "travelers": request.traveler_count,
                        "budget": str(request.budget_total),
                        "interests": request.interests,
                        "pace": request.pace,
                        "must_visit": request.must_visit,
                        "avoid_places": request.avoid_places,
                    },
                    "attempt": attempt,
                    "previous_failures": [
                        {
                            "constraint_id": failure.constraint_id,
                            "message": failure.message,
                            "evidence": dict(failure.evidence),
                        }
                        for failure in failures
                    ],
                    "candidates": candidates,
                    "required_selection_count": request.days * 2,
                },
                ensure_ascii=False,
                default=str,
            ),
            text_format=PlanSelection,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise DomainError(
                ErrorCode.PLAN_VALIDATION_FAILED,
                "模型没有返回可解析的地点选择",
            )
        lookup = {candidate.place.place_id: candidate for candidate in context.places}
        invalid_ids = [place_id for place_id in parsed.selected_place_ids if place_id not in lookup]
        if invalid_ids:
            raise DomainError(
                ErrorCode.PLAN_VALIDATION_FAILED,
                "模型选择了候选集合之外的地点",
                details={"invalid_place_ids": invalid_ids},
            )
        required_count = request.days * 2
        selected = [lookup[place_id] for place_id in parsed.selected_place_ids]
        if not selected:
            raise DomainError(
                ErrorCode.PLAN_VALIDATION_FAILED,
                "模型没有选择任何候选地点",
            )
        selected = [selected[index % len(selected)] for index in range(required_count)]
        selected_ids = {candidate.place.place_id for candidate in selected}
        remainder = [
            candidate
            for candidate in context.places
            if candidate.place.place_id not in selected_ids
        ]
        ordered_context = replace(context, places=tuple((*selected, *remainder)))
        return await self._assembler.generate(
            request,
            ordered_context,
            attempt=attempt,
            failures=failures,
        )


def _merge(existing: tuple[str, ...], new: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys((*existing, *(value for value in new if value.strip()))))
