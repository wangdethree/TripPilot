"""Create task, plan version, idempotency and event tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260729_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "planning_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("access_token_hash", sa.LargeBinary(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("workflow_step", sa.String(length=64), nullable=True),
        sa.Column("request_draft", postgresql.JSONB(), nullable=False),
        sa.Column("confirmed_request", postgresql.JSONB(), nullable=True),
        sa.Column("parent_task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("result_plan_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("result_plan_version", sa.Integer(), nullable=True),
        sa.Column("attempt_number", sa.SmallInteger(), nullable=False),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("lease_owner", sa.String(length=128), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "next_run_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("row_version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "attempt_number BETWEEN 0 AND 3",
            name="ck_planning_tasks_attempt_number",
        ),
        sa.ForeignKeyConstraint(["parent_task_id"], ["planning_tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("access_token_hash"),
    )
    op.create_index(
        "ix_planning_tasks_lease",
        "planning_tasks",
        ["lease_expires_at"],
    )
    op.create_index(
        "ix_planning_tasks_runnable",
        "planning_tasks",
        ["status", "next_run_at"],
        postgresql_where=sa.text("status IN ('PLANNING', 'REPLANNING')"),
    )
    op.create_table(
        "plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("access_token_hash", sa.LargeBinary(), nullable=False),
        sa.Column("latest_version", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("access_token_hash"),
    )
    op.create_index("ix_plans_expires_at", "plans", ["expires_at"])
    op.create_table(
        "idempotency_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope", sa.String(length=128), nullable=False),
        sa.Column("key_hash", sa.LargeBinary(), nullable=False),
        sa.Column("request_hash", sa.LargeBinary(), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("response_document", postgresql.JSONB(), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "scope",
            "key_hash",
            name="uq_idempotency_scope_key",
        ),
    )
    op.create_index(
        "ix_idempotency_records_expires_at",
        "idempotency_records",
        ["expires_at"],
    )
    op.create_table(
        "plan_versions",
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_by_task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("based_on_version", sa.Integer(), nullable=True),
        sa.Column("request_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("plan_document", postgresql.JSONB(), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column("content_hash", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by_task_id"], ["planning_tasks.id"]),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("plan_id", "version"),
        sa.UniqueConstraint(
            "plan_id",
            "version",
            name="uq_plan_versions_plan_version",
        ),
    )
    op.create_table(
        "task_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("document", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["planning_tasks.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_task_events_task_created",
        "task_events",
        ["task_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_task_events_task_created", table_name="task_events")
    op.drop_table("task_events")
    op.drop_table("plan_versions")
    op.drop_index(
        "ix_idempotency_records_expires_at",
        table_name="idempotency_records",
    )
    op.drop_table("idempotency_records")
    op.drop_index("ix_plans_expires_at", table_name="plans")
    op.drop_table("plans")
    op.drop_index("ix_planning_tasks_runnable", table_name="planning_tasks")
    op.drop_index("ix_planning_tasks_lease", table_name="planning_tasks")
    op.drop_table("planning_tasks")
