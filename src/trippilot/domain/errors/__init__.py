"""Domain failures use stable codes and never expose implementation details."""

from collections.abc import Mapping, Sequence

from trippilot.domain.enums import ErrorCode


class DomainError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        details: Mapping[str, object] | None = None,
        suggested_actions: Sequence[str] = (),
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = dict(details or {})
        self.suggested_actions = tuple(suggested_actions)


class ValidationError(DomainError):
    def __init__(
        self,
        message: str,
        *,
        field: str | None = None,
        details: Mapping[str, object] | None = None,
    ) -> None:
        merged_details = dict(details or {})
        if field is not None:
            merged_details["field"] = field
        super().__init__(ErrorCode.VALIDATION_ERROR, message, details=merged_details)


class InvalidStateTransitionError(DomainError):
    def __init__(self, current: str, target: str) -> None:
        super().__init__(
            ErrorCode.VALIDATION_ERROR,
            f"任务不能从 {current} 转换到 {target}",
            details={"current_status": current, "target_status": target},
        )


__all__ = [
    "DomainError",
    "InvalidStateTransitionError",
    "ValidationError",
]
