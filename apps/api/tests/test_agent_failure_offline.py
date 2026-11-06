"""Failure routing only: no database sessions, proposals, or provider requests."""
from types import SimpleNamespace
from unittest.mock import AsyncMock
import uuid

import httpx
import pytest

from main import app
from intentra.database import get_db
from intentra.routes import agents
from intentra.routes.auth import current_user
from intentra.services.agent_proposals import AgentProposalError


@pytest.mark.asyncio
async def test_handled_generation_failure_remains_503_through_middleware(monkeypatch):
    db = SimpleNamespace(rollback=AsyncMock())
    create = AsyncMock(side_effect=AgentProposalError(
        "Purchase proposal generation is unavailable. Your request was not evaluated.", 503))
    monkeypatch.setattr(agents, "create_proposal", create)
    overrides = app.dependency_overrides.copy()
    app.dependency_overrides.update({
        get_db: lambda: db,
        current_user: lambda: SimpleNamespace(id=uuid.uuid4()),
        agents.agent_provider_dependency: lambda: SimpleNamespace(mode="OLLAMA"),
        agents.agent_registry_dependency: lambda: None,
    })
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/agents/proposals", json={"request": "Buy an item"},
                                         headers={"Idempotency-Key": str(uuid.uuid4()),
                                                  "Origin": "http://localhost:3000"})
        assert response.status_code == 503
        assert response.json() == {"detail": str(create.side_effect)}
        assert "X-Intentra-Correlation-ID" in response.headers
        create.assert_awaited_once()
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(overrides)
