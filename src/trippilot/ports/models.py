"""Model ports keep provider SDK objects outside the application core."""

from typing import Protocol

from trippilot.application.dto import PlanningContext, RequirementDraft
from trippilot.domain.models import ConstraintResult, TravelRequest, TripPlan


class RequirementExtractorPort(Protocol):
    async def extract(
        self,
        message: str,
        *,
        existing: RequirementDraft | None = None,
    ) -> RequirementDraft: ...


class PlanGeneratorPort(Protocol):
    async def generate(
        self,
        request: TravelRequest,
        context: PlanningContext,
        *,
        attempt: int,
        failures: tuple[ConstraintResult, ...] = (),
    ) -> TripPlan: ...
