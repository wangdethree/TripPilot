"""Static travel data adapters used when external providers are disabled."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from trippilot.application.dto import PlaceCandidate, RouteEstimate, WeatherDay
from trippilot.domain.enums import (
    FreshnessStatus,
    InformationType,
    TransportMode,
)
from trippilot.domain.models import PlaceRef, SourceRecord
from trippilot.domain.value_objects import Money

_CITY_DATA: dict[str, tuple[tuple[str, tuple[str, ...], bool, str, str], ...]] = {
    "成都": (
        ("武侯祠", ("历史", "建筑"), True, "50", "三国文化与古建"),
        ("成都博物馆", ("历史", "博物馆"), True, "0", "城市历史综合展览"),
        ("杜甫草堂", ("历史", "自然"), False, "50", "诗歌文化与园林"),
        ("人民公园", ("美食", "自然"), False, "0", "茶馆与城市生活"),
        ("东郊记忆", ("艺术", "摄影"), False, "0", "工业遗址艺术街区"),
        ("四川美术馆", ("艺术", "博物馆"), True, "0", "近现代艺术展览"),
    ),
    "西安": (
        ("陕西历史博物馆", ("历史", "博物馆"), True, "0", "周秦汉唐文物"),
        ("西安城墙", ("历史", "建筑"), False, "54", "明代城墙"),
        ("大雁塔", ("历史", "建筑"), False, "40", "唐代佛教建筑"),
        ("大唐不夜城", ("夜景", "美食"), False, "0", "夜间步行街区"),
        ("西安博物院", ("历史", "博物馆"), True, "0", "古都历史展览"),
        ("回民街区域", ("美食",), False, "0", "地方小吃街区"),
    ),
}


class FakePlaceTool:
    async def search(
        self,
        city: str,
        interests: tuple[str, ...],
    ) -> tuple[PlaceCandidate, ...]:
        del interests
        rows = _CITY_DATA.get(city, _CITY_DATA["成都"])
        retrieved_at = datetime.now(UTC)
        candidates: list[PlaceCandidate] = []
        for index, (name, tags, indoor, ticket, description) in enumerate(rows):
            source_id = f"fake-place-{city}-{index}"
            source = SourceRecord(
                source_id=source_id,
                provider="TripPilot Fake Places",
                title=f"{city}{name}演示数据",
                retrieved_at=retrieved_at,
                information_type=InformationType.PLACE,
                related_item_ids=(),
                freshness_status=FreshnessStatus.FRESH,
            )
            place = PlaceRef(
                place_id=f"fake:{city}:{index}",
                name=name,
                address=f"{city}{name}",
                latitude=Decimal("30.0000") + Decimal(index) / 100,
                longitude=Decimal("104.0000") + Decimal(index) / 100,
                source_ids=(source_id,),
            )
            candidates.append(
                PlaceCandidate(
                    place=place,
                    interest_tags=tags,
                    indoor=indoor,
                    recommended_duration_minutes=120,
                    ticket_cost=Money.of(ticket),
                    description=description,
                    source=source,
                )
            )
        return tuple(candidates)


class FakeWeatherTool:
    async def get_forecast(
        self,
        city: str,
        start_date: date,
        end_date: date,
    ) -> tuple[WeatherDay, ...]:
        retrieved_at = datetime.now(UTC)
        days: list[WeatherDay] = []
        current = start_date
        while current <= end_date:
            source_id = f"fake-weather-{city}-{current.isoformat()}"
            source = SourceRecord(
                source_id=source_id,
                provider="TripPilot Fake Weather",
                title=f"{city}{current.isoformat()}演示天气",
                retrieved_at=retrieved_at,
                information_type=InformationType.WEATHER,
                related_item_ids=(),
                freshness_status=FreshnessStatus.FRESH,
            )
            days.append(
                WeatherDay(
                    date=current,
                    summary="多云, 适合普通城市活动",
                    severe_alert=False,
                    precipitation_probability=20,
                    source=source,
                )
            )
            current += timedelta(days=1)
        return tuple(days)


class FakeRouteTool:
    async def estimate(
        self,
        origin: PlaceRef,
        destination: PlaceRef,
        modes: tuple[TransportMode, ...],
    ) -> RouteEstimate:
        del modes
        source = SourceRecord(
            source_id=f"fake-route-{origin.place_id}-{destination.place_id}",
            provider="TripPilot Fake Routes",
            title=f"{origin.name}至{destination.name}演示路线",
            retrieved_at=datetime.now(UTC),
            information_type=InformationType.ROUTE,
            related_item_ids=(),
            freshness_status=FreshnessStatus.FRESH,
        )
        return RouteEstimate(
            duration_minutes=30,
            distance_meters=5000,
            mode=TransportMode.PUBLIC_TRANSIT,
            cost=Money.of("5"),
            source=source,
        )
