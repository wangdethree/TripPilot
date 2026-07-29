from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from trippilot.infrastructure.postgres import Base, Database, TaskLeaseRepository


def test_metadata_contains_versioned_persistence_tables() -> None:
    assert {
        "planning_tasks",
        "plans",
        "plan_versions",
        "idempotency_records",
        "task_events",
    } <= set(Base.metadata.tables)


@pytest.mark.asyncio
async def test_lease_repository_claims_rows_and_commits() -> None:
    first_id = uuid4()
    second_id = uuid4()
    rows = [
        SimpleNamespace(
            id=first_id,
            lease_owner=None,
            lease_expires_at=None,
        ),
        SimpleNamespace(
            id=second_id,
            lease_owner=None,
            lease_expires_at=None,
        ),
    ]

    class ScalarResult:
        def all(self) -> list[SimpleNamespace]:
            return rows

    session = AsyncMock(spec=AsyncSession)
    session.scalars.return_value = ScalarResult()
    repository = TaskLeaseRepository()
    claimed = await repository.claim_batch(
        session,
        owner="worker-1",
        batch_size=2,
        lease_seconds=30,
    )
    assert claimed == (first_id, second_id)
    assert all(row.lease_owner == "worker-1" for row in rows)
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_database_engine_can_be_created_without_connecting() -> None:
    database = Database("postgresql+psycopg://user:pass@localhost/test")
    assert database.engine.url.database == "test"
    await database.dispose()
