"""Application data transfer objects used across use-case boundaries."""

from dataclasses import dataclass, field
from datetime import date, time

from trippilot.domain.enums import Pace, TransportMode
from trippilot.domain.models import PlaceRef, SourceRecord, TravelRequest
from trippilot.domain.value_objects import Money, TravelDateRange


@dataclass(frozen=True, slots=True)
class RequirementDraft:
    destination_city: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    days: int | None = None
    traveler_count: int | None = None
    budget_total: Money | None = None
    budget_includes_accommodation: bool | None = None
    interests: tuple[str, ...] = ()
    pace: Pace = Pace.MODERATE
    transport_preferences: tuple[TransportMode, ...] = (
        TransportMode.PUBLIC_TRANSIT,
        TransportMode.WALKING,
    )
    must_visit: tuple[str, ...] = ()
    avoid_places: tuple[str, ...] = ()
    dietary_restrictions: tuple[str, ...] = ()
    mobility_constraints: tuple[str, ...] = ()
    daily_start_time: time = time(9)
    daily_end_time: time = time(21)
    assumptions: tuple[str, ...] = ()
    ambiguities: tuple[str, ...] = ()

    @property
    def missing_fields(self) -> tuple[str, ...]:
        missing: list[str] = []
        for field_name in (
            "destination_city",
            "start_date",
            "traveler_count",
            "budget_total",
            "budget_includes_accommodation",
        ):
            if getattr(self, field_name) is None:
                missing.append(field_name)
        if self.end_date is None and self.days is None:
            missing.append("end_date_or_days")
        if not self.interests:
            missing.append("interests")
        return tuple(missing)

    def to_confirmed_request(self, *, today: date) -> TravelRequest:
        if self.missing_fields:
            raise ValueError(f"需求仍缺少字段: {', '.join(self.missing_fields)}")
        assert self.destination_city is not None
        assert self.start_date is not None
        assert self.traveler_count is not None
        assert self.budget_total is not None
        assert self.budget_includes_accommodation is not None
        if self.end_date is None:
            assert self.days is not None
            date_range = TravelDateRange.from_days(self.start_date, self.days)
        else:
            date_range = TravelDateRange(self.start_date, self.end_date)
            if self.days is not None and self.days != date_range.days:
                raise ValueError("结束日期与旅行天数不一致")
        date_range.validate_not_past(today)
        return TravelRequest(
            destination_city=self.destination_city,
            date_range=date_range,
            traveler_count=self.traveler_count,
            budget_total=self.budget_total,
            budget_includes_accommodation=self.budget_includes_accommodation,
            interests=self.interests,
            pace=self.pace,
            transport_preferences=self.transport_preferences,
            must_visit=self.must_visit,
            avoid_places=self.avoid_places,
            dietary_restrictions=self.dietary_restrictions,
            mobility_constraints=self.mobility_constraints,
            daily_start_time=self.daily_start_time,
            daily_end_time=self.daily_end_time,
        )


@dataclass(frozen=True, slots=True)
class PlaceCandidate:
    place: PlaceRef
    interest_tags: tuple[str, ...]
    indoor: bool
    recommended_duration_minutes: int
    ticket_cost: Money
    description: str
    source: SourceRecord


@dataclass(frozen=True, slots=True)
class WeatherDay:
    date: date
    summary: str
    severe_alert: bool
    precipitation_probability: int
    source: SourceRecord


@dataclass(frozen=True, slots=True)
class PlanningContext:
    places: tuple[PlaceCandidate, ...]
    weather: tuple[WeatherDay, ...]
    sources: tuple[SourceRecord, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class RouteEstimate:
    duration_minutes: int
    distance_meters: int
    mode: TransportMode
    cost: Money
    source: SourceRecord


@dataclass(frozen=True, slots=True)
class ResourceUsage:
    model_calls: int = 0
    tool_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    candidate_count: int = 0


@dataclass(frozen=True, slots=True)
class ExecutionLimits:
    max_model_calls: int = 10
    max_tool_calls: int = 20
    max_tokens: int = 40_000
    max_candidates: int = 3
