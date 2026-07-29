"""Travel plan aggregate and immutable nested value objects."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal

from trippilot.domain.enums import (
    CheckStatus,
    ConstraintCategory,
    ConstraintSeverity,
    CostConfidence,
    EnvironmentType,
    FreshnessStatus,
    InformationType,
    TaskStatus,
    TimelineItemType,
    TransportMode,
)
from trippilot.domain.errors import ValidationError
from trippilot.domain.models.request import TravelRequest
from trippilot.domain.value_objects import Money


@dataclass(frozen=True, slots=True)
class PlaceRef:
    place_id: str
    name: str
    source_ids: tuple[str, ...]
    address: str | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None

    def __post_init__(self) -> None:
        if not self.place_id or not self.name:
            raise ValidationError("地点标识和名称不能为空", field="location")


@dataclass(frozen=True, slots=True)
class CostEstimate:
    amount: Money | None
    confidence: CostConfidence
    covers_travelers: int
    description: str
    source_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.covers_travelers < 1:
            raise ValidationError("费用覆盖人数必须大于 0", field="covers_travelers")
        if self.confidence is CostConfidence.UNKNOWN and self.amount is not None:
            raise ValidationError("未知费用的金额必须为空", field="amount")
        if self.confidence is not CostConfidence.UNKNOWN and self.amount is None:
            raise ValidationError("已知或估算费用必须包含金额", field="amount")
        if self.amount is not None and self.amount.amount < 0:
            raise ValidationError("费用不得为负数", field="amount")


@dataclass(frozen=True, slots=True)
class ActivityDetails:
    duration_minutes: int
    environment: EnvironmentType
    reservation_required: bool | None
    opening_hours_status: CheckStatus
    interest_tags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TransitDetails:
    origin: PlaceRef
    destination: PlaceRef
    transport_mode: TransportMode
    duration_minutes: int | None
    distance_meters: int | None = None


@dataclass(frozen=True, slots=True)
class MealDetails:
    cuisine_types: tuple[str, ...]
    estimated_cost_per_person: CostEstimate
    specific_restaurant_verified: bool


@dataclass(frozen=True, slots=True)
class RestDetails:
    flexible: bool
    minimum_duration_minutes: int


TimelineDetails = ActivityDetails | TransitDetails | MealDetails | RestDetails


@dataclass(frozen=True, slots=True)
class TimelineItem:
    item_id: str
    item_type: TimelineItemType
    start_time: time
    end_time: time
    title: str
    location: PlaceRef | None
    description: str
    reason: str
    estimated_cost: CostEstimate
    source_ids: tuple[str, ...]
    warnings: tuple[str, ...]
    details: TimelineDetails

    def __post_init__(self) -> None:
        if self.end_time <= self.start_time:
            raise ValidationError("时间线结束时间必须晚于开始时间", field="end_time")
        if not self.item_id or not self.title:
            raise ValidationError("时间线条目标识和标题不能为空", field="item_id")
        if self.item_type is not TimelineItemType.REST and self.location is None:
            raise ValidationError("非休息条目必须包含地点", field="location")
        expected_type: type[object]
        expected_type = {
            TimelineItemType.ACTIVITY: ActivityDetails,
            TimelineItemType.TRANSIT: TransitDetails,
            TimelineItemType.MEAL: MealDetails,
            TimelineItemType.REST: RestDetails,
        }[self.item_type]
        if not isinstance(self.details, expected_type):
            raise ValidationError("时间线类型与详情类型不一致", field="details")
        if isinstance(self.details, ActivityDetails):
            duration = _duration_minutes(self.start_time, self.end_time)
            if self.details.duration_minutes != duration:
                raise ValidationError("活动停留时间与时间线不一致", field="duration_minutes")


@dataclass(frozen=True, slots=True)
class CostBucket:
    known: Money
    estimated: Money

    @property
    def total(self) -> Money:
        return self.known + self.estimated


@dataclass(frozen=True, slots=True)
class BudgetSummary:
    accommodation: CostBucket
    transportation: CostBucket
    tickets: CostBucket
    meals: CostBucket
    other: CostBucket
    reserve: Money
    known_total: Money
    estimated_total: Money
    budget_scope_total: Money
    unknown_items: tuple[CostEstimate, ...]
    remaining_budget: Money

    @property
    def travel_total(self) -> Money:
        return self.known_total + self.estimated_total


@dataclass(frozen=True, slots=True)
class ConstraintResult:
    constraint_id: str
    category: ConstraintCategory
    severity: ConstraintSeverity
    status: CheckStatus
    message: str
    evidence: Mapping[str, object]
    affected_item_ids: tuple[str, ...] = ()
    suggested_actions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SourceRecord:
    source_id: str
    provider: str
    title: str
    retrieved_at: datetime
    information_type: InformationType
    related_item_ids: tuple[str, ...]
    freshness_status: FreshnessStatus
    url: str | None = None


@dataclass(frozen=True, slots=True)
class PlanChange:
    from_version: int
    to_version: int
    requested_change: str
    target_dates: tuple[date, ...]
    target_item_ids: tuple[str, ...]
    change_summary: tuple[str, ...]
    preserved_dates: tuple[date, ...]
    changed_at: datetime

    def __post_init__(self) -> None:
        if self.to_version != self.from_version + 1:
            raise ValidationError("新版本号必须等于上一版本加 1", field="to_version")


@dataclass(frozen=True, slots=True)
class DayPlan:
    date: date
    theme: str
    timeline_items: tuple[TimelineItem, ...]
    daily_budget: BudgetSummary
    daily_warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        item_ids = [item.item_id for item in self.timeline_items]
        if len(item_ids) != len(set(item_ids)):
            raise ValidationError("同一日时间线条目标识不能重复", field="item_id")


@dataclass(frozen=True, slots=True)
class TripPlan:
    version: int
    request_snapshot: TravelRequest
    status: TaskStatus
    days: tuple[DayPlan, ...]
    budget_summary: BudgetSummary
    constraint_results: tuple[ConstraintResult, ...]
    assumptions: tuple[str, ...]
    sources: tuple[SourceRecord, ...]
    change_history: tuple[PlanChange, ...]
    generated_at: datetime
    updated_at: datetime
    plan_id: str | None = None

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValidationError("行程版本必须大于 0", field="version")
        if self.status not in {TaskStatus.COMPLETED, TaskStatus.PARTIAL}:
            raise ValidationError("可展示行程只能是 COMPLETED 或 PARTIAL", field="status")
        if len(self.days) != self.request_snapshot.days:
            raise ValidationError("每日计划数量必须与旅行天数一致", field="days")
        if any(not self.request_snapshot.date_range.contains(day.date) for day in self.days):
            raise ValidationError("每日计划日期必须位于旅行日期范围内", field="date")


def _duration_minutes(start: time, end: time) -> int:
    return (end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)
