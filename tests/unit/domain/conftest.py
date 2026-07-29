from collections.abc import Iterable
from datetime import UTC, date, datetime, time
from decimal import Decimal

import pytest

from trippilot.domain.enums import (
    CheckStatus,
    CostConfidence,
    EnvironmentType,
    FreshnessStatus,
    InformationType,
    TaskStatus,
    TimelineItemType,
    TransportMode,
)
from trippilot.domain.models import (
    ActivityDetails,
    CostEstimate,
    DayPlan,
    MealDetails,
    PlaceRef,
    SourceRecord,
    TimelineItem,
    TransitDetails,
    TravelRequest,
    TripPlan,
)
from trippilot.domain.services import calculate_budget
from trippilot.domain.value_objects import Money, TravelDateRange


@pytest.fixture
def travel_request() -> TravelRequest:
    return TravelRequest(
        destination_city="成都",
        date_range=TravelDateRange(date(2030, 10, 2), date(2030, 10, 2)),
        traveler_count=2,
        budget_total=Money.of("2000"),
        budget_includes_accommodation=False,
        interests=("历史", "美食"),
    )


def place(name: str) -> PlaceRef:
    return PlaceRef(
        place_id=f"place-{name}",
        name=name,
        address=f"成都市{name}",
        latitude=Decimal("30.67"),
        longitude=Decimal("104.06"),
        source_ids=("source-place",),
    )


def known_cost(amount: str, description: str = "费用") -> CostEstimate:
    return CostEstimate(
        amount=Money.of(amount),
        confidence=CostConfidence.KNOWN,
        covers_travelers=2,
        description=description,
        source_ids=("source-price",),
    )


def activity(
    item_id: str,
    name: str,
    start: time,
    end: time,
    *,
    interest_tags: tuple[str, ...] = ("历史",),
    opening_status: CheckStatus = CheckStatus.PASS,
    amount: str = "100",
) -> TimelineItem:
    duration = (end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)
    location = place(name)
    return TimelineItem(
        item_id=item_id,
        item_type=TimelineItemType.ACTIVITY,
        start_time=start,
        end_time=end,
        title=name,
        location=location,
        description=f"参观{name}",
        reason="符合兴趣",
        estimated_cost=known_cost(amount, "门票"),
        source_ids=("source-place", "source-price"),
        warnings=(),
        details=ActivityDetails(
            duration_minutes=duration,
            environment=EnvironmentType.INDOOR,
            reservation_required=False,
            opening_hours_status=opening_status,
            interest_tags=interest_tags,
        ),
    )


def transit(
    item_id: str,
    origin_name: str,
    destination_name: str,
    start: time,
    end: time,
    *,
    duration: int | None = 30,
) -> TimelineItem:
    origin = place(origin_name)
    destination = place(destination_name)
    return TimelineItem(
        item_id=item_id,
        item_type=TimelineItemType.TRANSIT,
        start_time=start,
        end_time=end,
        title=f"前往{destination_name}",
        location=destination,
        description="公共交通",
        reason="连接相邻活动",
        estimated_cost=known_cost("10", "交通"),
        source_ids=("source-route",),
        warnings=(),
        details=TransitDetails(
            origin=origin,
            destination=destination,
            transport_mode=TransportMode.PUBLIC_TRANSIT,
            duration_minutes=duration,
            distance_meters=5000,
        ),
    )


def meal(item_id: str, name: str, start: time, end: time) -> TimelineItem:
    cost = known_cost("100", "两人用餐")
    return TimelineItem(
        item_id=item_id,
        item_type=TimelineItemType.MEAL,
        start_time=start,
        end_time=end,
        title=name,
        location=place(name),
        description="川菜用餐区域",
        reason="靠近前后活动",
        estimated_cost=cost,
        source_ids=("source-place", "source-price"),
        warnings=(),
        details=MealDetails(
            cuisine_types=("川菜",),
            estimated_cost_per_person=known_cost("50", "人均"),
            specific_restaurant_verified=False,
        ),
    )


def make_plan(
    request: TravelRequest,
    items: Iterable[TimelineItem],
    *,
    accommodation: CostEstimate | None = None,
    sources: tuple[SourceRecord, ...] | None = None,
) -> TripPlan:
    item_tuple = tuple(items)
    accommodation_costs = () if accommodation is None else (accommodation,)
    budget = calculate_budget(
        item_tuple,
        budget_total=request.budget_total,
        accommodation_costs=accommodation_costs,
        budget_includes_accommodation=request.budget_includes_accommodation,
    )
    day = DayPlan(
        date=request.date_range.start,
        theme="历史与美食",
        timeline_items=item_tuple,
        daily_budget=budget,
    )
    now = datetime(2030, 1, 1, tzinfo=UTC)
    default_sources = (
        SourceRecord(
            source_id="source-place",
            provider="fake",
            title="固定地点数据",
            retrieved_at=now,
            information_type=InformationType.PLACE,
            related_item_ids=tuple(item.item_id for item in item_tuple),
            freshness_status=FreshnessStatus.FRESH,
        ),
    )
    return TripPlan(
        version=1,
        request_snapshot=request,
        status=TaskStatus.COMPLETED,
        days=(day,),
        budget_summary=budget,
        constraint_results=(),
        assumptions=request.explicit_defaults,
        sources=default_sources if sources is None else sources,
        change_history=(),
        generated_at=now,
        updated_at=now,
    )
