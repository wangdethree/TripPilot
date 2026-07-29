"""FastAPI application and versioned REST endpoints."""

import hashlib
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from typing import Annotated

import structlog
from fastapi import Depends, FastAPI, Header, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import RequestResponseEndpoint

from trippilot.bootstrap import Settings, build_container
from trippilot.domain.enums import ErrorCode, TaskStatus
from trippilot.domain.errors import DomainError
from trippilot.execution import RuntimeTask, TaskCoordinator
from trippilot.infrastructure.observability import (
    configure_observability,
    instrument_fastapi,
)
from trippilot.interfaces.http.schemas import (
    AddMessageRequest,
    CommandAcceptedResponse,
    ConfirmationRequest,
    CreateTaskRequest,
    ErrorBody,
    ErrorResponse,
    SavedPlanResponse,
    TaskCreatedResponse,
    TaskViewResponse,
)
from trippilot.interfaces.http.serialization import to_primitive

API_PREFIX = "/api/v1"


def create_app(settings: Settings | None = None) -> FastAPI:
    container = build_container(settings or Settings())
    configure_observability(log_level=container.settings.log_level)
    logger = structlog.get_logger("trippilot.http")

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await container.close()

    app = FastAPI(
        title="TripPilot API",
        version="0.1.0",
        description="可控、可测试的国内城市旅行规划 Agent",
        lifespan=lifespan,
    )
    app.state.container = container
    app.add_middleware(
        CORSMiddleware,
        allow_origins=container.settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "If-Match"],
    )

    @app.middleware("http")
    async def trace_middleware(
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        started_at = time.perf_counter()
        trace_id = str(uuid.uuid4())
        request.state.trace_id = trace_id
        structlog.contextvars.bind_contextvars(trace_id=trace_id)
        try:
            response = await call_next(request)
            response.headers["trace_id"] = trace_id
            logger.info(
                "http_request_completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
            )
            return response
        finally:
            structlog.contextvars.clear_contextvars()

    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
        payload = _error_response(request, exc)
        return JSONResponse(
            status_code=_status_for_error(exc),
            content=payload.model_dump(mode="json"),
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        payload = ErrorResponse(
            error=ErrorBody(
                code=ErrorCode.VALIDATION_ERROR,
                message=str(exc),
                details={},
                suggested_actions=[],
            ),
            trace_id=_trace_id(request),
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=payload.model_dump(mode="json"),
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        errors = to_primitive(exc.errors())
        payload = ErrorResponse(
            error=ErrorBody(
                code=ErrorCode.VALIDATION_ERROR,
                message="请求格式或字段不合法",
                details={"errors": errors},
                suggested_actions=["检查请求字段"],
            ),
            trace_id=_trace_id(request),
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=payload.model_dump(mode="json"),
        )

    def coordinator() -> TaskCoordinator:
        return container.coordinator

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "mode": container.settings.model_provider}

    @app.post(
        f"{API_PREFIX}/planning-tasks",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=TaskCreatedResponse,
    )
    async def create_task(
        body: CreateTaskRequest,
        service: Annotated[TaskCoordinator, Depends(coordinator)],
        idempotency_key: Annotated[
            str | None,
            Header(alias="Idempotency-Key"),
        ] = None,
    ) -> TaskCreatedResponse:
        async def operation() -> TaskCreatedResponse:
            token, task = await service.create(body.message)
            return TaskCreatedResponse(
                task_token=token,
                status=task.status,
                row_version=task.row_version,
            )

        return await container.idempotency.execute(
            scope="create-task",
            key=idempotency_key,
            request={"message": body.message},
            operation=operation,
        )

    @app.post(
        f"{API_PREFIX}/planning-tasks/current/messages",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=CommandAcceptedResponse,
    )
    async def add_message(
        body: AddMessageRequest,
        service: Annotated[TaskCoordinator, Depends(coordinator)],
        token: Annotated[str, Depends(_bearer_token)],
        if_match: Annotated[str | None, Header(alias="If-Match")] = None,
        idempotency_key: Annotated[
            str | None,
            Header(alias="Idempotency-Key"),
        ] = None,
    ) -> CommandAcceptedResponse:
        expected_version = _parse_etag(if_match)

        async def operation() -> CommandAcceptedResponse:
            task = await service.add_message(
                token,
                body.message,
                expected_version=expected_version,
            )
            return CommandAcceptedResponse(status=task.status, row_version=task.row_version)

        return await container.idempotency.execute(
            scope=_command_scope("add-message", token),
            key=idempotency_key,
            request={"message": body.message, "expected_version": expected_version},
            operation=operation,
        )

    @app.get(
        f"{API_PREFIX}/planning-tasks/current",
        response_model=TaskViewResponse,
    )
    async def get_task(
        response: Response,
        service: Annotated[TaskCoordinator, Depends(coordinator)],
        token: Annotated[str, Depends(_bearer_token)],
    ) -> TaskViewResponse:
        task = await service.get(token)
        response.headers["ETag"] = f'"{task.row_version}"'
        if not task.status.is_terminal:
            response.headers["Retry-After"] = "1"
        return _task_view(task)

    @app.post(
        f"{API_PREFIX}/planning-tasks/current/confirmation",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=CommandAcceptedResponse,
    )
    async def confirm_task(
        body: ConfirmationRequest,
        service: Annotated[TaskCoordinator, Depends(coordinator)],
        token: Annotated[str, Depends(_bearer_token)],
        if_match: Annotated[str | None, Header(alias="If-Match")] = None,
        idempotency_key: Annotated[
            str | None,
            Header(alias="Idempotency-Key"),
        ] = None,
    ) -> CommandAcceptedResponse:
        if not body.confirmed:
            raise DomainError(ErrorCode.CONFIRMATION_REQUIRED, "请修改需求后再确认")
        expected_version = _parse_etag(if_match)

        async def operation() -> CommandAcceptedResponse:
            task = await service.confirm(
                token,
                expected_version=expected_version,
                today=date.today(),
            )
            return CommandAcceptedResponse(status=task.status, row_version=task.row_version)

        return await container.idempotency.execute(
            scope=_command_scope("confirm", token),
            key=idempotency_key,
            request={"confirmed": True, "expected_version": expected_version},
            operation=operation,
        )

    @app.post(
        f"{API_PREFIX}/planning-tasks/current/cancellation",
        response_model=CommandAcceptedResponse,
    )
    async def cancel_task(
        service: Annotated[TaskCoordinator, Depends(coordinator)],
        token: Annotated[str, Depends(_bearer_token)],
        idempotency_key: Annotated[
            str | None,
            Header(alias="Idempotency-Key"),
        ] = None,
    ) -> CommandAcceptedResponse:
        async def operation() -> CommandAcceptedResponse:
            task = await service.cancel(token)
            return CommandAcceptedResponse(status=task.status, row_version=task.row_version)

        return await container.idempotency.execute(
            scope=_command_scope("cancel", token),
            key=idempotency_key,
            request={},
            operation=operation,
        )

    @app.get(f"{API_PREFIX}/planning-tasks/current/result", response_model=None)
    async def get_result(
        service: Annotated[TaskCoordinator, Depends(coordinator)],
        token: Annotated[str, Depends(_bearer_token)],
    ) -> JSONResponse:
        task = await service.get(token)
        if task.result is not None:
            return JSONResponse(content=to_primitive(task.result))
        if task.error is not None:
            raise task.error
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={"status": task.status, "result_available": False},
        )

    @app.post(
        f"{API_PREFIX}/planning-tasks/current/saved-plan",
        status_code=status.HTTP_201_CREATED,
        response_model=SavedPlanResponse,
    )
    async def save_result(
        service: Annotated[TaskCoordinator, Depends(coordinator)],
        token: Annotated[str, Depends(_bearer_token)],
        idempotency_key: Annotated[
            str | None,
            Header(alias="Idempotency-Key"),
        ] = None,
    ) -> SavedPlanResponse:
        async def operation() -> SavedPlanResponse:
            plan_token, plan = await service.save_result(token)
            return SavedPlanResponse(
                plan_token=plan_token,
                version=plan.version,
                expires_at=datetime.now(UTC) + timedelta(days=30),
            )

        return await container.idempotency.execute(
            scope=_command_scope("save-plan", token),
            key=idempotency_key,
            request={},
            operation=operation,
        )

    @app.get(f"{API_PREFIX}/plans/current", response_model=None)
    async def get_plan(
        service: Annotated[TaskCoordinator, Depends(coordinator)],
        token: Annotated[str, Depends(_bearer_token)],
    ) -> JSONResponse:
        plan = await service.get_plan(token)
        return JSONResponse(
            content=to_primitive(plan),
            headers={"ETag": f'"{plan.version}"'},
        )

    @app.delete(
        f"{API_PREFIX}/plans/current",
        status_code=status.HTTP_204_NO_CONTENT,
    )
    async def delete_plan(
        service: Annotated[TaskCoordinator, Depends(coordinator)],
        token: Annotated[str, Depends(_bearer_token)],
        idempotency_key: Annotated[
            str | None,
            Header(alias="Idempotency-Key"),
        ] = None,
    ) -> Response:
        async def operation() -> Response:
            await service.delete_plan(token)
            return Response(status_code=status.HTTP_204_NO_CONTENT)

        return await container.idempotency.execute(
            scope=_command_scope("delete-plan", token),
            key=idempotency_key,
            request={},
            operation=operation,
        )

    instrument_fastapi(app)
    return app


def _task_view(task: RuntimeTask) -> TaskViewResponse:
    summary_source: object = task.confirmed_request or task.draft
    next_actions = {
        TaskStatus.COLLECTING_REQUIREMENTS: ["补充缺失信息"],
        TaskStatus.AWAITING_CONFIRMATION: ["确认需求", "继续修改"],
        TaskStatus.PLANNING: ["等待规划完成", "取消任务"],
        TaskStatus.COMPLETED: ["查看结果", "保存行程"],
        TaskStatus.PARTIAL: ["查看结果与未知信息", "保存行程"],
        TaskStatus.NEEDS_USER_INPUT: ["调整冲突约束"],
        TaskStatus.FAILED: ["查看错误建议", "重新创建任务"],
        TaskStatus.CANCELLED: ["重新创建任务"],
        TaskStatus.REPLANNING: ["等待重规划完成", "取消任务"],
    }[task.status]
    summary = to_primitive(summary_source)
    usage = to_primitive(task.usage)
    assert isinstance(summary, dict)
    assert isinstance(usage, dict)
    return TaskViewResponse(
        status=task.status,
        workflow_step=task.workflow_step,
        request_summary=summary,
        missing_fields=list(task.draft.missing_fields),
        assumptions=list(task.draft.assumptions),
        unresolved_constraints=[],
        attempt_number=task.usage.candidate_count,
        resource_usage=usage,
        result_available=task.result is not None,
        next_actions=next_actions,
        updated_at=task.updated_at,
        row_version=task.row_version,
    )


def _bearer_token(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> str:
    if authorization is None or not authorization.startswith("Bearer "):
        raise DomainError(ErrorCode.PLAN_NOT_AVAILABLE, "缺少可用的访问令牌")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise DomainError(ErrorCode.PLAN_NOT_AVAILABLE, "缺少可用的访问令牌")
    return token


def _parse_etag(value: str | None) -> int | None:
    if value is None:
        return None
    normalized = value.strip().strip('"')
    if not normalized.isdigit():
        raise ValueError("If-Match 必须是任务版本号")
    return int(normalized)


def _command_scope(command: str, token: str) -> str:
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    return f"{command}:{token_hash}"


def _error_response(request: Request, error: DomainError) -> ErrorResponse:
    return ErrorResponse(
        error=ErrorBody(
            code=error.code,
            message=error.message,
            details=error.details,
            suggested_actions=list(error.suggested_actions),
        ),
        trace_id=_trace_id(request),
    )


def _trace_id(request: Request) -> str:
    return str(getattr(request.state, "trace_id", uuid.uuid4()))


def _status_for_error(error: DomainError) -> int:
    if error.code is ErrorCode.PLAN_NOT_AVAILABLE:
        return status.HTTP_401_UNAUTHORIZED
    if error.code in {ErrorCode.VERSION_CONFLICT, ErrorCode.REPLAN_LIMIT_REACHED}:
        return status.HTTP_409_CONFLICT
    if error.code is ErrorCode.RATE_LIMITED:
        return status.HTTP_429_TOO_MANY_REQUESTS
    if error.code in {
        ErrorCode.VALIDATION_ERROR,
        ErrorCode.CONFIRMATION_REQUIRED,
        ErrorCode.UNSUPPORTED_SCOPE,
    }:
        return status.HTTP_422_UNPROCESSABLE_CONTENT
    if error.code in {ErrorCode.TOOL_TIMEOUT, ErrorCode.MODEL_UNAVAILABLE}:
        return status.HTTP_503_SERVICE_UNAVAILABLE
    return status.HTTP_500_INTERNAL_SERVER_ERROR


app = create_app()
