"""Origin middleware checks that never open a database connection."""

import pytest
from httpx import ASGITransport, AsyncClient

from main import app


@pytest.mark.asyncio
async def test_untrusted_origin_is_rejected_before_a_state_changing_route(monkeypatch):
    monkeypatch.setenv("INTENTRA_ALLOWED_ORIGINS", "https://preview.example.test")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://api.example.test") as client:
        response = await client.post("/not-a-real-route", headers={"Origin": "https://attacker.example.test"})

    assert response.status_code == 403
    assert response.json()["code"] == "ORIGIN_REJECTED"
    assert response.headers["X-Intentra-Error-Code"] == "ORIGIN_REJECTED"


@pytest.mark.asyncio
async def test_explicit_preview_origin_reaches_route_dispatch(monkeypatch):
    monkeypatch.setenv("INTENTRA_ALLOWED_ORIGINS", "https://preview.example.test")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://api.example.test") as client:
        response = await client.post("/not-a-real-route", headers={"Origin": "https://preview.example.test"})

    # The path does not exist, but it was not rejected by origin protection.
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_health_reports_only_safe_deployment_diagnostics():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://api.example.test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["origin_protection"] == "enabled"
    assert isinstance(response.json()["database_configured"], bool)
