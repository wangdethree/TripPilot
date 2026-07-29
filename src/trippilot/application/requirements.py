"""Requirement collection and confirmation use cases."""

from datetime import date

from trippilot.application.dto import RequirementDraft
from trippilot.domain.models import TravelRequest
from trippilot.ports import RequirementExtractorPort


class RequirementService:
    def __init__(self, extractor: RequirementExtractorPort) -> None:
        self._extractor = extractor

    async def collect(
        self,
        message: str,
        *,
        existing: RequirementDraft | None = None,
    ) -> RequirementDraft:
        if not message.strip():
            raise ValueError("旅行描述不能为空")
        return await self._extractor.extract(message, existing=existing)

    def confirm(self, draft: RequirementDraft, *, today: date) -> TravelRequest:
        return draft.to_confirmed_request(today=today)
