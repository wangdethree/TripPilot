"""Structured logging, redaction and OpenTelemetry setup."""

from __future__ import annotations

import logging
from collections.abc import MutableMapping
from typing import Any

import structlog
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

_SENSITIVE_FRAGMENTS = (
    "authorization",
    "api_key",
    "apikey",
    "idempotency",
    "password",
    "secret",
    "token",
)


def redact_sensitive_values(
    _: object,
    __: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    """Remove known secret-bearing fields before rendering a log event."""

    for key in tuple(event_dict):
        normalized = key.lower()
        if any(fragment in normalized for fragment in _SENSITIVE_FRAGMENTS):
            event_dict[key] = "[REDACTED]"
    return event_dict


def configure_observability(*, log_level: str) -> None:
    """Configure deterministic JSON logs once per process."""

    logging.basicConfig(level=log_level.upper(), format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            redact_sensitive_values,
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelNamesMapping().get(log_level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def instrument_fastapi(app: Any) -> None:
    """Attach standard HTTP spans without exporting secrets or request bodies."""

    FastAPIInstrumentor.instrument_app(
        app,
        excluded_urls="health",
    )
