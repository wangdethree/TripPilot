"""Inclusive travel date range."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from trippilot.domain.errors import ValidationError


@dataclass(frozen=True, slots=True)
class TravelDateRange:
    start: date
    end: date

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValidationError("结束日期不得早于开始日期", field="end_date")
        if not 1 <= self.days <= 3:
            raise ValidationError("第一版只支持 1-3 日行程", field="days")

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    @classmethod
    def from_days(cls, start: date, days: int) -> TravelDateRange:
        if not 1 <= days <= 3:
            raise ValidationError("第一版只支持 1-3 日行程", field="days")
        return cls(start=start, end=start + timedelta(days=days - 1))

    def validate_not_past(self, today: date) -> None:
        if self.start < today:
            raise ValidationError("开始日期不得早于今天", field="start_date")

    def contains(self, value: date) -> bool:
        return self.start <= value <= self.end
