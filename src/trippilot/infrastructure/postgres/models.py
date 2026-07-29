"""Relational metadata and versioned JSONB documents."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class PlanningTaskRow(Base):
    __tablename__ = "planning_tasks"
    __table_args__ = (
        CheckConstraint(
            "attempt_number BETWEEN 0 AND 3",
            name="ck_planning_tasks_attempt_number",
        ),
        Index(
            "ix_planning_tasks_runnable",
            "status",
            "next_run_at",
            postgresql_where="status IN ('PLANNING', 'REPLANNING')",
        ),
        Index("ix_planning_tasks_lease", "lease_expires_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    access_token_hash: Mapped[bytes] = mapped_column(LargeBinary, unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    workflow_step: Mapped[str | None] = mapped_column(String(64))
    request_draft: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    confirmed_request: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    parent_task_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("planning_tasks.id"),
    )
    result_plan_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    result_plan_version: Mapped[int | None] = mapped_column(Integer)
    attempt_number: Mapped[int] = mapped_column(SmallInteger, default=0)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    lease_owner: Mapped[str | None] = mapped_column(String(128))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    row_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PlanRow(Base):
    __tablename__ = "plans"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    access_token_hash: Mapped[bytes] = mapped_column(LargeBinary, unique=True, nullable=False)
    latest_version: Mapped[int] = mapped_column(Integer, default=1)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class PlanVersionRow(Base):
    __tablename__ = "plan_versions"
    __table_args__ = (UniqueConstraint("plan_id", "version", name="uq_plan_versions_plan_version"),)

    plan_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("plans.id", ondelete="CASCADE"),
        primary_key=True,
    )
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_by_task_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("planning_tasks.id"),
    )
    based_on_version: Mapped[int | None] = mapped_column(Integer)
    request_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB)
    plan_document: Mapped[dict[str, object]] = mapped_column(JSONB)
    schema_version: Mapped[str] = mapped_column(String(32), default="1.0")
    content_hash: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class IdempotencyRecordRow(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (UniqueConstraint("scope", "key_hash", name="uq_idempotency_scope_key"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    scope: Mapped[str] = mapped_column(String(128), nullable=False)
    key_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    request_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    response_document: Mapped[dict[str, object]] = mapped_column(JSONB)
    resource_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class TaskEventRow(Base):
    __tablename__ = "task_events"
    __table_args__ = (Index("ix_task_events_task_created", "task_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("planning_tasks.id", ondelete="CASCADE"),
    )
    event_type: Mapped[str] = mapped_column(String(64))
    document: Mapped[dict[str, object]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
