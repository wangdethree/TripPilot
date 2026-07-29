"""Deterministic fake models for local development, CI and demonstrations."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta

from trippilot.application.dto import PlaceCandidate, PlanningContext, RequirementDraft
from trippilot.domain.enums import (
    CheckStatus,
    CostConfidence,
    EnvironmentType,
    Pace,
    TaskStatus,
    TimelineItemType,
    TransportMode,
)
from trippilot.domain.models import (
    ActivityDetails,
    ConstraintResult,
    CostEstimate,
    DayPlan,
    MealDetails,
    RestDetails,
    TimelineItem,
    TransitDetails,
    TravelRequest,
    TripPlan,
)
from trippilot.domain.services import calculate_budget
from trippilot.domain.value_objects import Money

_CITY_NAMES = (
    "成都",
    "西安",
    "北京",
    "上海",
    "杭州",
    "重庆",
    "南京",
    "苏州",
    "广州",
    "深圳",
)
_INTEREST_NAMES = (
    "历史",
    "美食",
    "博物馆",
    "自然",
    "摄影",
    "建筑",
    "亲子",
    "艺术",
    "夜景",
    "购物",
)


class FakeRequirementExtractor:
    """A bounded parser, intentionally not pretending to understand arbitrary Chinese."""

    async def extract(
        self,
        message: str,
        *,
        existing: RequirementDraft | None = None,
    ) -> RequirementDraft:
        draft = existing or RequirementDraft()
        city = next((name for name in _CITY_NAMES if name in message), None)
        iso_dates = tuple(
            date.fromisoformat(value) for value in re.findall(r"\b(20\d{2}-\d{2}-\d{2})\b", message)
        )
        days_match = re.search(r"([1-3])\s*[天日]", message)
        chinese_days = next(
            (value for text, value in (("一天", 1), ("两天", 2), ("三天", 3)) if text in message),
            None,
        )
        people_match = re.search(r"([1-8])\s*(?:人|个(?:大人|人))", message)
        chinese_people = 2 if "两个人" in message or "两人" in message else None
        budget_match = re.search(r"预算(?:是|为|大约|约)?\s*([0-9]+(?:\.[0-9]{1,2})?)", message)
        if budget_match is None:
            budget_match = re.search(r"([0-9]+(?:\.[0-9]{1,2})?)\s*元", message)
        includes_accommodation: bool | None = None
        if any(text in message for text in ("不含住宿", "不包含住宿", "住宿另算")):
            includes_accommodation = False
        elif any(text in message for text in ("包含住宿", "含住宿", "住宿算在预算")):
            includes_accommodation = True
        interests = tuple(name for name in _INTEREST_NAMES if name in message)
        pace = draft.pace
        if "轻松" in message:
            pace = Pace.RELAXED
        elif "紧凑" in message or "特种兵" in message:
            pace = Pace.INTENSIVE
        elif "适中" in message:
            pace = Pace.MODERATE
        start_date = iso_dates[0] if iso_dates else draft.start_date
        end_date = iso_dates[1] if len(iso_dates) > 1 else draft.end_date
        days = int(days_match.group(1)) if days_match else chinese_days
        traveler_count = (
            int(people_match.group(1)) if people_match else chinese_people or draft.traveler_count
        )
        budget = Money.of(budget_match.group(1)) if budget_match else draft.budget_total
        return replace(
            draft,
            destination_city=city or draft.destination_city,
            start_date=start_date,
            end_date=end_date,
            days=days or draft.days,
            traveler_count=traveler_count,
            budget_total=budget,
            budget_includes_accommodation=(
                includes_accommodation
                if includes_accommodation is not None
                else draft.budget_includes_accommodation
            ),
            interests=tuple(dict.fromkeys((*draft.interests, *interests))),
            pace=pace,
        )


class FakePlanGenerator:
    """Produces a complete candidate only from verified planning context."""

    async def generate(
        self,
        request: TravelRequest,
        context: PlanningContext,
        *,
        attempt: int,
        failures: tuple[ConstraintResult, ...] = (),
    ) -> TripPlan:
        del failures
        ranked = sorted(
            context.places,
            key=lambda candidate: (
                not bool(set(candidate.interest_tags) & set(request.interests)),
                candidate.ticket_cost.amount,
            ),
        )
        if attempt > 1:
            ranked = sorted(ranked, key=lambda candidate: candidate.ticket_cost.amount)
        required_count = request.days * 2
        selected = _repeat_to_length(ranked, required_count)
        generated_at = datetime.now(UTC)
        days: list[DayPlan] = []
        all_items: list[TimelineItem] = []
        for index in range(request.days):
            first, second = selected[index * 2 : index * 2 + 2]
            current_date = request.date_range.start + timedelta(days=index)
            day_items = _build_day(index, first, second, request.traveler_count)
            all_items.extend(day_items)
            daily_budget = calculate_budget(
                day_items,
                budget_total=request.budget_total,
                budget_includes_accommodation=request.budget_includes_accommodation,
            )
            days.append(
                DayPlan(
                    date=current_date,
                    theme=f"{first.interest_tags[0]}与{second.interest_tags[0]}",
                    timeline_items=day_items,
                    daily_budget=daily_budget,
                )
            )
        budget = calculate_budget(
            all_items,
            budget_total=request.budget_total,
            budget_includes_accommodation=request.budget_includes_accommodation,
        )
        sources = tuple(
            dict.fromkeys(
                (
                    *(candidate.source for candidate in selected),
                    *(weather.source for weather in context.weather),
                    *context.sources,
                )
            )
        )
        return TripPlan(
            version=1,
            request_snapshot=request,
            status=TaskStatus.COMPLETED,
            days=tuple(days),
            budget_summary=budget,
            constraint_results=(),
            assumptions=request.explicit_defaults,
            sources=sources,
            change_history=(),
            generated_at=generated_at,
            updated_at=generated_at,
        )


def _repeat_to_length[T](values: Sequence[T], length: int) -> list[T]:
    if not values:
        raise ValueError("地点工具没有返回候选")
    return [values[index % len(values)] for index in range(length)]


def _build_day(
    day_index: int,
    first: PlaceCandidate,
    second: PlaceCandidate,
    traveler_count: int,
) -> tuple[TimelineItem, ...]:
    prefix = f"d{day_index + 1}"
    return (
        _activity(f"{prefix}-a1", first, time(9), time(11), traveler_count),
        _transit(f"{prefix}-t1", first, second, time(11), time(11, 30), traveler_count),
        _meal(f"{prefix}-m1", second, time(11, 30), time(12, 30), traveler_count),
        _activity(f"{prefix}-a2", second, time(13), time(15), traveler_count),
        _rest(f"{prefix}-r1", time(15), time(16), traveler_count),
    )


def _activity(
    item_id: str,
    candidate: PlaceCandidate,
    start: time,
    end: time,
    traveler_count: int,
) -> TimelineItem:
    return TimelineItem(
        item_id=item_id,
        item_type=TimelineItemType.ACTIVITY,
        start_time=start,
        end_time=end,
        title=candidate.place.name,
        location=candidate.place,
        description=candidate.description,
        reason=f"匹配偏好: {', '.join(candidate.interest_tags)}",
        estimated_cost=CostEstimate(
            amount=candidate.ticket_cost * traveler_count,
            confidence=CostConfidence.KNOWN,
            covers_travelers=traveler_count,
            description="门票与活动费用",
            source_ids=(candidate.source.source_id,),
        ),
        source_ids=(candidate.source.source_id,),
        warnings=(),
        details=ActivityDetails(
            duration_minutes=120,
            environment=EnvironmentType.INDOOR if candidate.indoor else EnvironmentType.OUTDOOR,
            reservation_required=False,
            opening_hours_status=CheckStatus.PASS,
            interest_tags=candidate.interest_tags,
        ),
    )


def _transit(
    item_id: str,
    origin: PlaceCandidate,
    destination: PlaceCandidate,
    start: time,
    end: time,
    traveler_count: int,
) -> TimelineItem:
    return TimelineItem(
        item_id=item_id,
        item_type=TimelineItemType.TRANSIT,
        start_time=start,
        end_time=end,
        title=f"前往{destination.place.name}",
        location=destination.place,
        description="公共交通约 30 分钟",
        reason="连接相邻活动",
        estimated_cost=CostEstimate(
            amount=Money.of("5") * traveler_count,
            confidence=CostConfidence.ESTIMATED,
            covers_travelers=traveler_count,
            description="市内交通",
        ),
        source_ids=(),
        warnings=("演示模式路线时间为固定估算",),
        details=TransitDetails(
            origin=origin.place,
            destination=destination.place,
            transport_mode=TransportMode.PUBLIC_TRANSIT,
            duration_minutes=30,
            distance_meters=5000,
        ),
    )


def _meal(
    item_id: str,
    nearby: PlaceCandidate,
    start: time,
    end: time,
    traveler_count: int,
) -> TimelineItem:
    per_person = CostEstimate(
        amount=Money.of("60"),
        confidence=CostConfidence.ESTIMATED,
        covers_travelers=1,
        description="人均餐饮",
    )
    return TimelineItem(
        item_id=item_id,
        item_type=TimelineItemType.MEAL,
        start_time=start,
        end_time=end,
        title=f"{nearby.place.name}附近用餐",
        location=nearby.place,
        description="选择符合饮食限制的本地餐饮区域",
        reason="靠近前后活动, 减少绕行",
        estimated_cost=CostEstimate(
            amount=Money.of("60") * traveler_count,
            confidence=CostConfidence.ESTIMATED,
            covers_travelers=traveler_count,
            description="团队餐饮",
        ),
        source_ids=(),
        warnings=("未核实具体餐厅, 请现场确认",),
        details=MealDetails(
            cuisine_types=("本地特色",),
            estimated_cost_per_person=per_person,
            specific_restaurant_verified=False,
        ),
    )


def _rest(
    item_id: str,
    start: time,
    end: time,
    traveler_count: int,
) -> TimelineItem:
    return TimelineItem(
        item_id=item_id,
        item_type=TimelineItemType.REST,
        start_time=start,
        end_time=end,
        title="休息与自由活动",
        location=None,
        description="为临时变化保留弹性",
        reason="降低连续活动强度",
        estimated_cost=CostEstimate(
            amount=Money.zero(),
            confidence=CostConfidence.ESTIMATED,
            covers_travelers=traveler_count,
            description="无固定费用",
        ),
        source_ids=(),
        warnings=(),
        details=RestDetails(flexible=True, minimum_duration_minutes=30),
    )
