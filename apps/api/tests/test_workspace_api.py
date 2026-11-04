import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from test_contract_integration import app, require_test_database
from intentra.routes.agents import agent_provider_dependency, agent_registry_dependency


def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:3000",
        headers={"Origin": "http://localhost:3000"})


@pytest.mark.asyncio
async def test_workspace_views_are_authenticated_and_owner_scoped(monkeypatch):
    require_test_database()
    suffix = uuid.uuid4().hex
    monkeypatch.setenv("PAYPAL_SANDBOX_MERCHANTS", '{"workspace_test_merchant":"PAYPAL-WORKSPACE-TEST"}')
    monkeypatch.delenv("PAYPAL_SANDBOX_CLIENT_ID", raising=False)
    monkeypatch.delenv("PAYPAL_SANDBOX_CLIENT_SECRET", raising=False)
    app.dependency_overrides.pop(agent_provider_dependency, None)
    app.dependency_overrides.pop(agent_registry_dependency, None)
    async with client() as anonymous:
        for path in ("/api/workspace/audit", "/api/workspace/security", "/api/workspace/analytics",
                     "/api/workspace/merchants", "/api/workspace/status"):
            assert (await anonymous.get(path)).status_code == 401

    async with client() as owner, client() as outsider:
        owner_registration = await owner.post("/api/auth/register", json={
            "email": f"workspace-owner-{suffix}@example.com", "password": "IntentraWorkspaceTest2026!"})
        assert owner_registration.status_code == 201, owner_registration.text
        outsider_registration = await outsider.post("/api/auth/register", json={
            "email": f"workspace-outsider-{suffix}@example.com", "password": "IntentraWorkspaceTest2026!"})
        assert outsider_registration.status_code == 201, outsider_registration.text
        contract = await owner.post("/api/contracts", json={
            "merchant_id": "workspace_test_merchant", "maximum_amount": "10.00", "currency": "USD"})
        assert contract.status_code == 201, contract.text
        contract_id = contract.json()["id"]
        approved = await owner.post(f"/api/contracts/{contract_id}/approve", json={"expected_version": 1})
        assert approved.status_code == 200
        evaluation = await owner.post("/api/payments/evaluate", json={
            "contract_id": contract_id, "merchant_id": "workspace_test_merchant",
            "amount": "2.00", "currency": "USD"})
        assert evaluation.status_code == 200

        audit = await owner.get("/api/workspace/audit?entity_type=contract&limit=10")
        assert audit.status_code == 200, audit.text
        assert {item["event_type"] for item in audit.json()["items"]} >= {"CONTRACT_CREATED", "CONTRACT_APPROVED"}
        assert all(item["related_ids"]["contract_id"] == contract_id for item in audit.json()["items"])
        assert (await owner.get(f"/api/workspace/audit?event_type=PAYMENT_EVALUATED:ALLOW")).json()["items"][0]["event_type"] == "PAYMENT_EVALUATED:ALLOW"
        assert (await outsider.get("/api/workspace/audit")).json()["items"] == []

        security = await owner.get("/api/workspace/security")
        assert security.status_code == 200, security.text
        assert security.json()["authenticated"] is True
        assert security.json()["current_session_valid"] is True
        assert security.json()["contracts"]["APPROVED"] == 1
        assert security.json()["policy_decisions"]["ALLOW"] == 1

        analytics = await owner.get("/api/workspace/analytics")
        assert analytics.status_code == 200, analytics.text
        assert analytics.json()["payments"]["count"] == 0
        assert analytics.json()["policy_decisions"]["ALLOW"] == 1
        assert analytics.json()["budget_by_contract"][0]["remaining_amount"] == "10.00"
        assert (await outsider.get("/api/workspace/analytics")).json()["payments"]["count"] == 0

        merchants = await owner.get("/api/workspace/merchants")
        assert merchants.status_code == 200
        assert merchants.json()["items"] == [{
            "internal_merchant_id": "workspace_test_merchant",
            "paypal_merchant_id": "PAYPAL-WORKSPACE-TEST",
            "trust_source": "server_configuration", "provider_live_verified": False,
        }]
        status = await owner.get("/api/workspace/status")
        assert status.status_code == 200
        assert status.json()["api"] == "available" and status.json()["database"] == "available"
        assert "client_secret" not in status.text.lower()
        monkeypatch.setenv("AGENT_LLM_ENABLED", "true")
        monkeypatch.setenv("AGENT_AI_PROVIDER", "unsupported-provider")
        misconfigured = await owner.get("/api/workspace/status")
        assert misconfigured.json()["llm_mode"] == "misconfigured"
    app.dependency_overrides.pop(agent_provider_dependency, None)
    app.dependency_overrides.pop(agent_registry_dependency, None)
