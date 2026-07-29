"""Confirmed travel request aggregate."""

from dataclasses import dataclass
from datetime import time

from trippilot.domain.enums import Pace, TransportMode
from trippilot.domain.errors import ValidationError
from trippilot.domain.value_objects import Money, TravelDateRange


@dataclass(frozen=True, slots=True)
class TravelRequest:
    destination_city: str
    date_range: TravelDateRange
    traveler_count: int
    budget_total: Money
    budget_includes_accommodation: bool
    interests: tuple[str, ...]
    pace: Pace = Pace.MODERATE
    accommodation_area: str | None = None
    transport_preferences: tuple[TransportMode, ...] = (
        TransportMode.PUBLIC_TRANSIT,
        TransportMode.WALKING,
    )
    must_visit: tuple[str, ...] = ()
    avoid_places: tuple[str, ...] = ()
    dietary_restrictions: tuple[str, ...] = ()
    mobility_constraints: tuple[str, ...] = ()
    daily_start_time: time = time(9, 0)
    daily_end_time: time = time(21, 0)
    special_requirements: tuple[str, ...] = ()
    language: str = "zh-CN"
    timezone: str = "Asia/Shanghai"

    def __post_init__(self) -> None:
        if not self.destination_city.strip():
            raise ValidationError("目的地城市不能为空", field="destination_city")
        if not 1 <= self.traveler_count <= 8:
            raise ValidationError("同行人数必须为 1-8 人", field="traveler_count")
        if self.budget_total.amount <= 0:
            raise ValidationError("总预算必须大于 0", field="budget_total")
        if not tuple(item.strip() for item in self.interests if item.strip()):
            raise ValidationError("至少需要一个兴趣偏好", field="interests")
        if self.daily_end_time <= self.daily_start_time:
            raise ValidationError(
                "每日结束时间必须晚于开始时间",
                field="daily_end_time",
            )
        if self.language != "zh-CN":
            raise ValidationError("第一版只支持简体中文", field="language")
        if self.timezone != "Asia/Shanghai":
            raise ValidationError("第一版固定使用中国标准时间", field="timezone")
        overlap = set(self.must_visit) & set(self.avoid_places)
        if overlap:
            raise ValidationError(
                "必去地点与避开地点不能冲突",
                details={"conflicting_places": sorted(overlap)},
            )

    @property
    def days(self) -> int:
        return self.date_range.days

    @property
    def explicit_defaults(self) -> tuple[str, ...]:
        defaults: list[str] = []
        if self.pace is Pace.MODERATE:
            defaults.append("旅行节奏采用默认值: 适中")
        if self.daily_start_time == time(9, 0) and self.daily_end_time == time(21, 0):
            defaults.append("每日活动时间采用默认值: 09:00-21:00")
        if self.transport_preferences == (
            TransportMode.PUBLIC_TRANSIT,
            TransportMode.WALKING,
        ):
            defaults.append("交通偏好采用默认值: 公共交通、步行")
        return tuple(defaults)
