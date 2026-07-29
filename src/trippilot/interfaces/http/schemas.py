"""Versioned HTTP request and response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from trippilot.domain.enums import TaskStatus


class CreateTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=2000)


class AddMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=2000)


class ConfirmationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmed: bool


class TaskCreatedResponse(BaseModel):
    task_token: str
    status: TaskStatus
    row_version: int
    poll_after_seconds: int = 1


class CommandAcceptedResponse(BaseModel):
    status: TaskStatus
    row_version: int
    poll_after_seconds: int = 1


class TaskViewResponse(BaseModel):
    status: TaskStatus
    workflow_step: str | None
    request_summary: dict[str, object]
    missing_fields: list[str]
    assumptions: list[str]
    unresolved_constraints: list[object]
    attempt_number: int
    resource_usage: dict[str, object]
    result_available: bool
    next_actions: list[str]
    updated_at: datetime
    row_version: int


class SavedPlanResponse(BaseModel):
    plan_token: str
    version: int
    expires_at: datetime


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, object]
    suggested_actions: list[str]


class ErrorResponse(BaseModel):
    error: ErrorBody
    trace_id: str
