"""Application facade for the explicit LangGraph planning workflow."""

from uuid import uuid4

from trippilot.agent.graph import PlanningGraph, PlanningState, build_planning_graph
from trippilot.application.dto import ResourceUsage
from trippilot.domain.models import TravelRequest, TripPlan
from trippilot.ports import PlacePort, PlanGeneratorPort, WeatherPort


class PlanningWorkflow:
    def __init__(
        self,
        *,
        places: PlacePort,
        weather: WeatherPort,
        generator: PlanGeneratorPort,
        max_candidates: int = 3,
    ) -> None:
        self._graph: PlanningGraph = build_planning_graph(
            places=places,
            weather=weather,
            generator=generator,
            max_candidates=max_candidates,
        )

    async def run(self, request: TravelRequest) -> tuple[TripPlan, ResourceUsage]:
        initial_state = PlanningState(request=request)
        result = await self._graph.ainvoke(
            initial_state,
            config={"configurable": {"thread_id": str(uuid4())}},
        )
        return result["final_plan"], result["usage"]
