"""Stable domain enumerations shared by the application and adapters."""

from enum import StrEnum


class Pace(StrEnum):
    RELAXED = "relaxed"
    MODERATE = "moderate"
    INTENSIVE = "intensive"


class TaskStatus(StrEnum):
    COLLECTING_REQUIREMENTS = "COLLECTING_REQUIREMENTS"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    PLANNING = "PLANNING"
    REPLANNING = "REPLANNING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    NEEDS_USER_INPUT = "NEEDS_USER_INPUT"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

    @property
    def is_terminal(self) -> bool:
        return self in {
            self.COMPLETED,
            self.PARTIAL,
            self.NEEDS_USER_INPUT,
            self.FAILED,
            self.CANCELLED,
        }


class WorkflowStep(StrEnum):
    EXTRACT_REQUEST = "extract_request"
    VALIDATE_REQUEST = "validate_request"
    AWAIT_CONFIRMATION = "await_confirmation"
    LOAD_PLANNING_CONTEXT = "load_planning_context"
    GENERATE_CANDIDATE = "generate_candidate"
    ENRICH_CANDIDATE = "enrich_candidate"
    VALIDATE_CANDIDATE = "validate_candidate"
    PREPARE_REPLAN = "prepare_replan"
    FINALIZE = "finalize"


class CheckStatus(StrEnum):
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class ConstraintSeverity(StrEnum):
    HARD = "HARD"
    SOFT = "SOFT"


class ConstraintCategory(StrEnum):
    REQUEST = "REQUEST"
    BUDGET = "BUDGET"
    TIME = "TIME"
    ROUTE = "ROUTE"
    WEATHER = "WEATHER"
    PACE = "PACE"
    PREFERENCE = "PREFERENCE"
    ACCESSIBILITY = "ACCESSIBILITY"
    OPENING_HOURS = "OPENING_HOURS"


class TimelineItemType(StrEnum):
    ACTIVITY = "ACTIVITY"
    TRANSIT = "TRANSIT"
    MEAL = "MEAL"
    REST = "REST"


class CostConfidence(StrEnum):
    KNOWN = "KNOWN"
    ESTIMATED = "ESTIMATED"
    UNKNOWN = "UNKNOWN"


class EnvironmentType(StrEnum):
    INDOOR = "INDOOR"
    OUTDOOR = "OUTDOOR"
    MIXED = "MIXED"


class FreshnessStatus(StrEnum):
    FRESH = "FRESH"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class InformationType(StrEnum):
    WEATHER = "WEATHER"
    PLACE = "PLACE"
    ROUTE = "ROUTE"
    PRICE = "PRICE"
    OPENING_HOURS = "OPENING_HOURS"


class TransportMode(StrEnum):
    PUBLIC_TRANSIT = "public_transit"
    WALKING = "walking"
    TAXI = "taxi"


class ErrorCode(StrEnum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNSUPPORTED_SCOPE = "UNSUPPORTED_SCOPE"
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
    TOOL_TIMEOUT = "TOOL_TIMEOUT"
    TOOL_NO_RESULT = "TOOL_NO_RESULT"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    PLAN_VALIDATION_FAILED = "PLAN_VALIDATION_FAILED"
    REPLAN_LIMIT_REACHED = "REPLAN_LIMIT_REACHED"
    COST_LIMIT_EXCEEDED = "COST_LIMIT_EXCEEDED"
    RATE_LIMITED = "RATE_LIMITED"
    TASK_CANCELLED = "TASK_CANCELLED"
    PLAN_NOT_AVAILABLE = "PLAN_NOT_AVAILABLE"
    VERSION_CONFLICT = "VERSION_CONFLICT"
    PERSISTENCE_FAILED = "PERSISTENCE_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
