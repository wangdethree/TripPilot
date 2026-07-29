"""PostgreSQL-backed task claiming with short leases."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from trippilot.infrastructure.postgres.models import PlanningTaskRow


class TaskLeaseRepository:
    async def claim_batch(
        self,
        session: AsyncSession,
        *,
        owner: str,
        batch_size: int,
        lease_seconds: int,
    ) -> tuple[UUID, ...]:
        now = datetime.now(UTC)
        statement: Select[tuple[PlanningTaskRow]] = (
            select(PlanningTaskRow)
            .where(
                PlanningTaskRow.status.in_(("PLANNING", "REPLANNING")),
                PlanningTaskRow.cancel_requested.is_(False),
                PlanningTaskRow.next_run_at <= now,
                (
                    PlanningTaskRow.lease_expires_at.is_(None)
                    | (PlanningTaskRow.lease_expires_at < now)
                ),
            )
            .order_by(PlanningTaskRow.next_run_at, PlanningTaskRow.created_at)
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
        rows = tuple((await session.scalars(statement)).all())
        lease_expires_at = now + timedelta(seconds=lease_seconds)
        for row in rows:
            row.lease_owner = owner
            row.lease_expires_at = lease_expires_at
        await session.commit()
        return tuple(row.id for row in rows)
