import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from trippilot.bootstrap import Settings
from trippilot.interfaces.http.app import create_app


@pytest.mark.asyncio
async def test_complete_api_flow() -> None:
    app = create_app(Settings())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        created = await client.post(
            "/api/v1/planning-tasks",
            json={"message": ("2030-10-02 去成都玩两天, 两个人, 预算 3000 元, 喜欢历史和美食")},
        )
        assert created.status_code == 202
        token = created.json()["task_token"]
        headers = {"Authorization": f"Bearer {token}"}
        assert created.json()["status"] == "COLLECTING_REQUIREMENTS"

        task_view = await client.get("/api/v1/planning-tasks/current", headers=headers)
        assert task_view.status_code == 200
        assert task_view.json()["missing_fields"] == ["budget_includes_accommodation"]
        row_version = task_view.json()["row_version"]

        supplemented = await client.post(
            "/api/v1/planning-tasks/current/messages",
            headers={**headers, "If-Match": f'"{row_version}"'},
            json={"message": "预算不包含住宿"},
        )
        assert supplemented.status_code == 202
        assert supplemented.json()["status"] == "AWAITING_CONFIRMATION"
        row_version = supplemented.json()["row_version"]

        confirmed = await client.post(
            "/api/v1/planning-tasks/current/confirmation",
            headers={**headers, "If-Match": f'"{row_version}"'},
            json={"confirmed": True},
        )
        assert confirmed.status_code == 202
        assert confirmed.json()["status"] == "PLANNING"

        for _ in range(40):
            status_response = await client.get(
                "/api/v1/planning-tasks/current",
                headers=headers,
            )
            if status_response.json()["status"] in {"COMPLETED", "PARTIAL"}:
                break
            await asyncio.sleep(0.025)
        assert status_response.json()["status"] == "COMPLETED"
        assert status_response.json()["result_available"] is True

        result = await client.get(
            "/api/v1/planning-tasks/current/result",
            headers=headers,
        )
        assert result.status_code == 200
        assert result.json()["budget_summary"]["known_total"].endswith(".00")
        assert len(result.json()["days"]) == 2

        saved = await client.post(
            "/api/v1/planning-tasks/current/saved-plan",
            headers=headers,
        )
        assert saved.status_code == 201
        plan_token = saved.json()["plan_token"]
        plan_headers = {"Authorization": f"Bearer {plan_token}"}

        opened = await client.get("/api/v1/plans/current", headers=plan_headers)
        assert opened.status_code == 200
        assert opened.headers["etag"] == '"1"'
        assert opened.json()["version"] == 1

        deleted = await client.delete("/api/v1/plans/current", headers=plan_headers)
        assert deleted.status_code == 204
        missing = await client.get("/api/v1/plans/current", headers=plan_headers)
        assert missing.status_code == 401
        assert missing.json()["error"]["code"] == "PLAN_NOT_AVAILABLE"

    await app.state.container.coordinator.close()


@pytest.mark.asyncio
async def test_api_rejects_invalid_auth_version_and_body() -> None:
    app = create_app(Settings())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        no_auth = await client.get("/api/v1/planning-tasks/current")
        assert no_auth.status_code == 401

        invalid_body = await client.post(
            "/api/v1/planning-tasks",
            json={"message": ""},
        )
        assert invalid_body.status_code == 422
        assert invalid_body.json()["error"]["code"] == "VALIDATION_ERROR"

        created = await client.post(
            "/api/v1/planning-tasks",
            json={"message": ("2030-10-02 去成都玩一天, 两个人, 预算 3000 元, 包含住宿, 喜欢历史")},
        )
        token = created.json()["task_token"]
        conflict = await client.post(
            "/api/v1/planning-tasks/current/confirmation",
            headers={
                "Authorization": f"Bearer {token}",
                "If-Match": '"999"',
            },
            json={"confirmed": True},
        )
        assert conflict.status_code == 409
        assert conflict.json()["error"]["code"] == "VERSION_CONFLICT"

    await app.state.container.coordinator.close()


@pytest.mark.asyncio
async def test_create_task_is_idempotent_and_rejects_key_reuse() -> None:
    app = create_app(Settings())
    transport = ASGITransport(app=app)
    headers = {"Idempotency-Key": "create-demo-1"}
    body = {"message": "2030-10-02 去成都玩一天, 两个人, 预算 3000 元, 包含住宿, 喜欢历史"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.post("/api/v1/planning-tasks", headers=headers, json=body)
        repeated = await client.post("/api/v1/planning-tasks", headers=headers, json=body)
        conflict = await client.post(
            "/api/v1/planning-tasks",
            headers=headers,
            json={"message": "2030-10-02 去西安玩一天, 两个人, 预算 3000 元"},
        )

    assert first.status_code == 202
    assert repeated.json() == first.json()
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "VERSION_CONFLICT"
    await app.state.container.coordinator.close()
