"""Allow-listed, read-only adapters for real travel data providers."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, cast

import httpx

from trippilot.application.dto import PlaceCandidate, WeatherDay
from trippilot.domain.enums import ErrorCode, FreshnessStatus, InformationType
from trippilot.domain.errors import DomainError
from trippilot.domain.models import PlaceRef, SourceRecord
from trippilot.domain.value_objects import Money

_OPEN_METEO_GEOCODING = "https://geocoding-api.open-meteo.com"
_OPEN_METEO_FORECAST = "https://api.open-meteo.com"
_AMAP = "https://restapi.amap.com"


class _FixedHostJsonClient:
    """Small reliability boundary that cannot be redirected to arbitrary hosts."""

    def __init__(self, base_url: str, *, timeout: float, max_retries: int) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(timeout),
            follow_redirects=False,
        )
        self._max_retries = max_retries

    async def get(self, path: str, params: dict[str, str | int | float]) -> dict[str, Any]:
        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.get(path, params=params)
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ValueError("provider response is not an object")
                return payload
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                recoverable = not isinstance(exc, httpx.HTTPStatusError) or (
                    exc.response.status_code == 429 or exc.response.status_code >= 500
                )
                if attempt >= self._max_retries or not recoverable:
                    raise DomainError(
                        ErrorCode.TOOL_TIMEOUT,
                        "外部旅行数据服务暂时不可用",
                        details={"provider": self._client.base_url.host},
                        suggested_actions=("稍后重试", "切换到演示数据模式"),
                    ) from exc
                await asyncio.sleep(0.1 * (2**attempt))
            except (TypeError, ValueError) as exc:
                raise DomainError(
                    ErrorCode.TOOL_NO_RESULT,
                    "外部旅行数据返回了无法识别的结果",
                    details={"provider": self._client.base_url.host},
                ) from exc
        raise AssertionError("retry loop must return or raise")

    async def close(self) -> None:
        await self._client.aclose()


class OpenMeteoWeatherTool:
    """Weather adapter using Open-Meteo geocoding and daily forecasts."""

    def __init__(self, *, timeout: float = 8.0, max_retries: int = 2) -> None:
        self._geocoding = _FixedHostJsonClient(
            _OPEN_METEO_GEOCODING,
            timeout=timeout,
            max_retries=max_retries,
        )
        self._forecast = _FixedHostJsonClient(
            _OPEN_METEO_FORECAST,
            timeout=timeout,
            max_retries=max_retries,
        )

    async def get_forecast(
        self,
        city: str,
        start_date: date,
        end_date: date,
    ) -> tuple[WeatherDay, ...]:
        geocoding = await self._geocoding.get(
            "/v1/search",
            {"name": city, "count": 1, "language": "zh", "countryCode": "CN"},
        )
        locations = geocoding.get("results")
        if not isinstance(locations, list) or not locations:
            raise DomainError(ErrorCode.TOOL_NO_RESULT, f"无法定位城市: {city}")
        location = locations[0]
        if not isinstance(location, dict):
            raise DomainError(ErrorCode.TOOL_NO_RESULT, f"无法定位城市: {city}")
        latitude = location.get("latitude")
        longitude = location.get("longitude")
        if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)):
            raise DomainError(ErrorCode.TOOL_NO_RESULT, f"城市坐标不可用: {city}")
        forecast = await self._forecast.get(
            "/v1/forecast",
            {
                "latitude": latitude,
                "longitude": longitude,
                "daily": "weather_code,precipitation_probability_max",
                "timezone": "Asia/Shanghai",
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
        )
        daily = forecast.get("daily")
        if not isinstance(daily, dict):
            raise DomainError(ErrorCode.TOOL_NO_RESULT, "天气服务没有返回逐日预报")
        dates = daily.get("time")
        codes = daily.get("weather_code")
        rain = daily.get("precipitation_probability_max")
        if not all(isinstance(value, list) for value in (dates, codes, rain)):
            raise DomainError(ErrorCode.TOOL_NO_RESULT, "天气服务没有返回完整逐日预报")
        date_values = cast(list[Any], dates)
        code_values = cast(list[Any], codes)
        rain_values = cast(list[Any], rain)
        retrieved_at = datetime.now(UTC)
        rows: list[WeatherDay] = []
        for raw_date, raw_code, raw_rain in zip(
            date_values,
            code_values,
            rain_values,
            strict=True,
        ):
            day = date.fromisoformat(str(raw_date))
            source_id = f"open-meteo:{city}:{day.isoformat()}"
            rows.append(
                WeatherDay(
                    date=day,
                    summary=_weather_summary(int(raw_code)),
                    severe_alert=int(raw_code) >= 95,
                    precipitation_probability=int(raw_rain or 0),
                    source=SourceRecord(
                        source_id=source_id,
                        provider="Open-Meteo",
                        title=f"{city} {day.isoformat()} 天气预报",
                        retrieved_at=retrieved_at,
                        information_type=InformationType.WEATHER,
                        related_item_ids=(),
                        freshness_status=FreshnessStatus.FRESH,
                        url="https://open-meteo.com/",
                    ),
                )
            )
        return tuple(rows)

    async def close(self) -> None:
        await asyncio.gather(self._geocoding.close(), self._forecast.close())


class AmapPlaceTool:
    """POI search adapter for mainland China using an AMap Web Service key."""

    def __init__(
        self,
        api_key: str,
        *,
        timeout: float = 8.0,
        max_retries: int = 2,
    ) -> None:
        self._api_key = api_key
        self._client = _FixedHostJsonClient(
            _AMAP,
            timeout=timeout,
            max_retries=max_retries,
        )

    async def search(
        self,
        city: str,
        interests: tuple[str, ...],
    ) -> tuple[PlaceCandidate, ...]:
        keywords = "|".join(interests[:5]) or "景点"
        payload = await self._client.get(
            "/v3/place/text",
            {
                "key": self._api_key,
                "keywords": keywords,
                "city": city,
                "citylimit": "true",
                "offset": 20,
                "page": 1,
                "extensions": "base",
            },
        )
        if payload.get("status") != "1":
            raise DomainError(
                ErrorCode.TOOL_NO_RESULT,
                "地点服务拒绝了本次查询",
                details={"provider": "amap", "info": str(payload.get("info", "unknown"))},
            )
        pois = payload.get("pois")
        if not isinstance(pois, list) or not pois:
            raise DomainError(ErrorCode.TOOL_NO_RESULT, f"没有找到 {city} 的候选地点")
        retrieved_at = datetime.now(UTC)
        candidates: list[PlaceCandidate] = []
        for poi in pois:
            candidate = _parse_amap_poi(poi, city, interests, retrieved_at)
            if candidate is not None:
                candidates.append(candidate)
        if not candidates:
            raise DomainError(ErrorCode.TOOL_NO_RESULT, "地点结果缺少有效坐标")
        return tuple(candidates[:12])

    async def close(self) -> None:
        await self._client.close()


def _parse_amap_poi(
    raw: object,
    city: str,
    interests: tuple[str, ...],
    retrieved_at: datetime,
) -> PlaceCandidate | None:
    if not isinstance(raw, dict):
        return None
    poi_id = raw.get("id")
    name = raw.get("name")
    location = raw.get("location")
    if not isinstance(poi_id, str) or not isinstance(name, str) or not isinstance(location, str):
        return None
    try:
        longitude_text, latitude_text = location.split(",", maxsplit=1)
        longitude = Decimal(longitude_text)
        latitude = Decimal(latitude_text)
    except (InvalidOperation, ValueError):
        return None
    source_id = f"amap-poi:{poi_id}"
    source = SourceRecord(
        source_id=source_id,
        provider="高德地图",
        title=f"{city}{name}地点信息",
        retrieved_at=retrieved_at,
        information_type=InformationType.PLACE,
        related_item_ids=(),
        freshness_status=FreshnessStatus.FRESH,
        url="https://lbs.amap.com/",
    )
    address = raw.get("address")
    return PlaceCandidate(
        place=PlaceRef(
            place_id=f"amap:{poi_id}",
            name=name,
            source_ids=(source_id,),
            address=address if isinstance(address, str) else None,
            latitude=latitude,
            longitude=longitude,
        ),
        interest_tags=interests,
        indoor=False,
        recommended_duration_minutes=120,
        ticket_cost=Money.zero(),
        description="来自高德地点检索, 开放时间与票价需要出发前再次确认",
        source=source,
    )


def _weather_summary(code: int) -> str:
    if code == 0:
        return "晴朗"
    if code <= 3:
        return "多云"
    if code in {45, 48}:
        return "有雾"
    if code <= 67:
        return "有雨"
    if code <= 77:
        return "有雪"
    if code <= 82:
        return "阵雨"
    if code <= 86:
        return "阵雪"
    return "雷暴天气"
