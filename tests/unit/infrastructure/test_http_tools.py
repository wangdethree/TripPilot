from __future__ import annotations

from datetime import date, datetime
from typing import Any

import httpx
import pytest

from trippilot.domain.enums import ErrorCode
from trippilot.domain.errors import DomainError
from trippilot.infrastructure.http.travel_tools import (
    AmapPlaceTool,
    OpenMeteoWeatherTool,
    _FixedHostJsonClient,
    _parse_amap_poi,
    _weather_summary,
)


class StubJsonClient:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, str | int | float]]] = []
        self.closed = False

    async def get(self, path: str, params: dict[str, str | int | float]) -> dict[str, Any]:
        self.calls.append((path, params))
        return self.responses.pop(0)

    async def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_fixed_host_client_retries_recoverable_status() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503, request=request)
        return httpx.Response(200, json={"ok": True}, request=request)

    service = _FixedHostJsonClient("https://example.test", timeout=1, max_retries=1)
    await service._client.aclose()
    service._client = httpx.AsyncClient(
        base_url="https://example.test",
        transport=httpx.MockTransport(handler),
    )

    assert await service.get("/data", {"q": "x"}) == {"ok": True}
    assert attempts == 2
    await service.close()


@pytest.mark.asyncio
async def test_fixed_host_client_maps_bad_response_to_domain_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": True}, request=request)

    service = _FixedHostJsonClient("https://example.test", timeout=1, max_retries=2)
    await service._client.aclose()
    service._client = httpx.AsyncClient(
        base_url="https://example.test",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(DomainError) as captured:
        await service.get("/data", {})
    assert captured.value.code is ErrorCode.TOOL_TIMEOUT
    await service.close()


@pytest.mark.asyncio
async def test_open_meteo_maps_verified_forecast() -> None:
    tool = OpenMeteoWeatherTool()
    await tool._geocoding.close()
    await tool._forecast.close()
    geocoding = StubJsonClient([{"results": [{"latitude": 30.67, "longitude": 104.06}]}])
    forecast = StubJsonClient(
        [
            {
                "daily": {
                    "time": ["2030-10-02", "2030-10-03"],
                    "weather_code": [1, 96],
                    "precipitation_probability_max": [20, 80],
                }
            }
        ]
    )
    tool._geocoding = geocoding  # type: ignore[assignment]
    tool._forecast = forecast  # type: ignore[assignment]

    result = await tool.get_forecast(
        "成都",
        date(2030, 10, 2),
        date(2030, 10, 3),
    )

    assert [day.summary for day in result] == ["多云", "雷暴天气"]
    assert result[1].severe_alert is True
    assert result[0].source.provider == "Open-Meteo"
    await tool.close()
    assert geocoding.closed and forecast.closed


@pytest.mark.asyncio
async def test_open_meteo_rejects_unknown_city() -> None:
    tool = OpenMeteoWeatherTool()
    await tool._geocoding.close()
    await tool._forecast.close()
    tool._geocoding = StubJsonClient([{"results": []}])  # type: ignore[assignment]
    tool._forecast = StubJsonClient([])  # type: ignore[assignment]

    with pytest.raises(DomainError) as captured:
        await tool.get_forecast(
            "不存在",
            date(2030, 10, 2),
            date(2030, 10, 2),
        )
    assert captured.value.code is ErrorCode.TOOL_NO_RESULT
    await tool.close()


@pytest.mark.asyncio
async def test_amap_maps_pois_and_rejects_provider_error() -> None:
    tool = AmapPlaceTool("secret")
    await tool._client.close()
    stub = StubJsonClient(
        [
            {
                "status": "1",
                "pois": [
                    {
                        "id": "B001",
                        "name": "成都博物馆",
                        "location": "104.066,30.657",
                        "address": "青羊区",
                    },
                    {"id": "broken"},
                ],
            },
            {"status": "0", "info": "INVALID_USER_KEY"},
        ]
    )
    tool._client = stub  # type: ignore[assignment]

    places = await tool.search("成都", ("历史", "博物馆"))
    assert len(places) == 1
    assert places[0].place.place_id == "amap:B001"
    assert places[0].ticket_cost.amount == 0

    with pytest.raises(DomainError) as captured:
        await tool.search("成都", ("历史",))
    assert captured.value.code is ErrorCode.TOOL_NO_RESULT
    await tool.close()
    assert stub.closed


def test_provider_parsing_boundaries() -> None:
    assert _parse_amap_poi(None, "成都", (), datetime.now()) is None
    assert _parse_amap_poi({}, "成都", (), datetime.now()) is None
    assert _weather_summary(0) == "晴朗"
    assert _weather_summary(45) == "有雾"
    assert _weather_summary(61) == "有雨"
    assert _weather_summary(75) == "有雪"
    assert _weather_summary(80) == "阵雨"
    assert _weather_summary(85) == "阵雪"
