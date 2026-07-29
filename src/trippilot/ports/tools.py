"""Read-only external travel data ports."""

from datetime import date
from typing import Protocol

from trippilot.application.dto import PlaceCandidate, RouteEstimate, WeatherDay
from trippilot.domain.enums import TransportMode
from trippilot.domain.models import PlaceRef


class WeatherPort(Protocol):
    async def get_forecast(
        self,
        city: str,
        start_date: date,
        end_date: date,
    ) -> tuple[WeatherDay, ...]: ...


class PlacePort(Protocol):
    async def search(
        self,
        city: str,
        interests: tuple[str, ...],
    ) -> tuple[PlaceCandidate, ...]: ...


class RoutePort(Protocol):
    async def estimate(
        self,
        origin: PlaceRef,
        destination: PlaceRef,
        modes: tuple[TransportMode, ...],
    ) -> RouteEstimate: ...
