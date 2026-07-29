"""Composition root for selecting fake or real adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from openai import AsyncOpenAI

from trippilot.application import (
    InMemoryIdempotencyStore,
    PlanningWorkflow,
    RequirementService,
    TokenService,
)
from trippilot.bootstrap.settings import Settings
from trippilot.execution import TaskCoordinator
from trippilot.infrastructure.fakes import (
    FakePlaceTool,
    FakePlanGenerator,
    FakeRequirementExtractor,
    FakeWeatherTool,
)
from trippilot.infrastructure.http import AmapPlaceTool, OpenMeteoWeatherTool
from trippilot.infrastructure.memory import InMemoryPlanRepository
from trippilot.infrastructure.openai import (
    OpenAIPlanGenerator,
    OpenAIRequirementExtractor,
)
from trippilot.ports import (
    PlacePort,
    PlanGeneratorPort,
    RequirementExtractorPort,
    WeatherPort,
)


@dataclass(slots=True)
class Container:
    settings: Settings
    coordinator: TaskCoordinator
    idempotency: InMemoryIdempotencyStore
    resources: tuple[AsyncCloseable, ...] = ()

    async def close(self) -> None:
        await self.coordinator.close()
        for resource in self.resources:
            await resource.close()


class AsyncCloseable(Protocol):
    async def close(self) -> None: ...


def build_container(settings: Settings) -> Container:
    extractor: RequirementExtractorPort
    generator: PlanGeneratorPort
    resources: list[AsyncCloseable] = []
    if settings.model_provider == "openai":
        if settings.openai_api_key is None:
            raise ValueError("使用 OpenAI 模式时必须配置 TRIPPILOT_OPENAI_API_KEY")
        client = AsyncOpenAI(
            api_key=settings.openai_api_key.get_secret_value(),
            base_url=settings.openai_base_url,
            timeout=30,
            max_retries=2,
        )
        resources.append(client)
        extractor = OpenAIRequirementExtractor(
            client,
            model=settings.extraction_model,
        )
        generator = OpenAIPlanGenerator(
            client,
            model=settings.planning_model,
        )
    elif settings.model_provider == "fake":
        extractor = FakeRequirementExtractor()
        generator = FakePlanGenerator()
    else:
        raise ValueError("TRIPPILOT_MODEL_PROVIDER 只能是 fake 或 openai")
    places: PlacePort
    weather: WeatherPort
    if settings.tool_provider == "real":
        if settings.amap_api_key is None:
            raise ValueError("使用真实旅行工具时必须配置 TRIPPILOT_AMAP_API_KEY")
        places = AmapPlaceTool(
            settings.amap_api_key.get_secret_value(),
            timeout=settings.tool_timeout_seconds,
            max_retries=settings.tool_max_retries,
        )
        weather = OpenMeteoWeatherTool(
            timeout=settings.tool_timeout_seconds,
            max_retries=settings.tool_max_retries,
        )
        resources.extend((places, weather))
    elif settings.tool_provider == "fake":
        places = FakePlaceTool()
        weather = FakeWeatherTool()
    else:
        raise ValueError("TRIPPILOT_TOOL_PROVIDER 只能是 fake 或 real")
    workflow = PlanningWorkflow(
        places=places,
        weather=weather,
        generator=generator,
    )
    coordinator = TaskCoordinator(
        requirements=RequirementService(extractor),
        planning=workflow,
        tokens=TokenService(settings.token_pepper.get_secret_value()),
        plans=InMemoryPlanRepository(),
    )
    return Container(
        settings=settings,
        coordinator=coordinator,
        idempotency=InMemoryIdempotencyStore(),
        resources=tuple(resources),
    )
