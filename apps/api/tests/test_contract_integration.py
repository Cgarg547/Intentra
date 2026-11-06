import asyncio
import os
import uuid

import pytest
from sqlalchemy.pool import NullPool
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from tests.integration_db_guard import (
    IntegrationDatabaseConfigurationError,
    configured_integration_database_url,
)


def require_test_database():
    try:
        raw_url = configured_integration_database_url(os.environ)
    except IntegrationDatabaseConfigurationError as exc:
        pytest.fail(str(exc), pytrace=False)

    if not raw_url:
        pytest.skip(
            "Integration tests require explicit DATABASE_URL",
            allow_module_level=True,
        )
    return raw_url


TEST_DATABASE_URL = require_test_database()

# The explicit CI URL is validated before the application database module can
# initialize its default engine or FastAPI imports it.
from intentra import database  # noqa: E402

database.engine = create_async_engine(
    TEST_DATABASE_URL,
    poolclass=NullPool,
)

database.SessionLocal = database.async_sessionmaker(
    database.engine,
    class_=database.AsyncSession,
    expire_on_commit=False,
)

# Import the app only after verifying the database target.
from main import app  # noqa: E402


@pytest.mark.asyncio
async def test_contract_lifecycle_and_owner_isolation():
    suffix = uuid.uuid4().hex
    password = "IntentraIntegrationTest2026!"

    transport = ASGITransport(app=app)

    async with (
        AsyncClient(
            transport=transport,
            base_url="http://localhost:3000",
            headers={"Origin": "http://localhost:3000"},
        ) as owner,
        AsyncClient(
            transport=transport,
            base_url="http://localhost:3000",
            headers={"Origin": "http://localhost:3000"},
        ) as outsider,
    ):
        for client, prefix in (
            (owner, "owner"),
            (outsider, "outsider"),
        ):
            response = await client.post(
                "/api/auth/register",
                json={
                    "email": f"{prefix}-{suffix}@example.com",
                    "password": password,
                },
            )
            assert response.status_code == 201, response.text

        response = await owner.post(
            "/api/contracts",
            json={
                "merchant_id": "paypal_test_merchant",
                "maximum_amount": "150.00",
                "currency": "USD",
            },
        )
        assert response.status_code == 201, response.text

        contract = response.json()
        contract_id = contract["id"]

        assert contract["status"] == "DRAFT"
        assert contract["version"] == 1

        contract_url = f"/api/contracts/{contract_id}"

        # Another authenticated user cannot read the contract.
        response = await outsider.get(contract_url)
        assert response.status_code == 404, response.text

        # Another authenticated user cannot approve it.
        response = await outsider.post(
            f"{contract_url}/approve",
            json={"expected_version": 1},
        )
        assert response.status_code == 404, response.text

        # The owner can approve it.
        response = await owner.post(
            f"{contract_url}/approve",
            json={"expected_version": 1},
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "APPROVED"
        assert response.json()["version"] == 2

        # Repeating approval must fail.
        response = await owner.post(
            f"{contract_url}/approve",
            json={"expected_version": 1},
        )
        assert response.status_code == 409, response.text

        # Another user cannot revoke it.
        response = await outsider.post(
            f"{contract_url}/revoke",
            json={"expected_version": 2},
        )
        assert response.status_code == 404, response.text

        # Stale version must fail.
        response = await owner.post(
            f"{contract_url}/revoke",
            json={"expected_version": 1},
        )
        assert response.status_code == 409, response.text

        # Correct version permits revocation.
        response = await owner.post(
            f"{contract_url}/revoke",
            json={"expected_version": 2},
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "REVOKED"
        assert response.json()["version"] == 3

        # Repeated revocation must fail.
        response = await owner.post(
            f"{contract_url}/revoke",
            json={"expected_version": 2},
        )
        assert response.status_code == 409, response.text

    # Verify the persisted audit history independently.
    engine = create_async_engine(TEST_DATABASE_URL)

    try:
        async with engine.connect() as connection:
            rows = (
                await connection.execute(
                    text(
                        """
                        SELECT event_type, contract_version
                        FROM audit_events
                        WHERE contract_id = :contract_id
                        ORDER BY contract_version
                        """
                    ),
                    {"contract_id": uuid.UUID(contract_id)},
                )
            ).all()

        assert rows == [
            ("CONTRACT_CREATED", 1),
            ("CONTRACT_APPROVED", 2),
            ("CONTRACT_REVOKED", 3),
        ]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_approval_only_succeeds_once():
    suffix = uuid.uuid4().hex

    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://localhost:3000",
        headers={"Origin": "http://localhost:3000"},
    ) as client:
        response = await client.post(
            "/api/auth/register",
            json={
                "email": f"concurrent-{suffix}@example.com",
                "password": "IntentraIntegrationTest2026!",
            },
        )
        assert response.status_code == 201, response.text

        response = await client.post(
            "/api/contracts",
            json={
                "merchant_id": "paypal_concurrency_test",
                "maximum_amount": "100.00",
                "currency": "USD",
            },
        )
        assert response.status_code == 201, response.text

        contract_id = response.json()["id"]
        approve_url = f"/api/contracts/{contract_id}/approve"

        async def attempt_approval():
            return await client.post(
                approve_url,
                json={"expected_version": 1},
            )

        first, second = await asyncio.gather(
            attempt_approval(),
            attempt_approval(),
        )

        statuses = sorted([
            first.status_code,
            second.status_code,
        ])

        assert statuses == [200, 409], (
            f"Unexpected concurrent results: {statuses}"
        )

        response = await client.get(
            f"/api/contracts/{contract_id}"
        )

        assert response.status_code == 200, response.text
        assert response.json()["status"] == "APPROVED"
        assert response.json()["version"] == 2

    engine = create_async_engine(TEST_DATABASE_URL)

    try:
        async with engine.connect() as connection:
            rows = (
                await connection.execute(
                    text(
                        """
                        SELECT event_type, contract_version
                        FROM audit_events
                        WHERE contract_id = :contract_id
                        ORDER BY contract_version
                        """
                    ),
                    {"contract_id": uuid.UUID(contract_id)},
                )
            ).all()

        assert rows == [
            ("CONTRACT_CREATED", 1),
            ("CONTRACT_APPROVED", 2),
        ]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_contract_listing_is_owner_scoped():
    suffix = uuid.uuid4().hex
    transport = ASGITransport(app=app)

    async with (
        AsyncClient(
            transport=transport,
            base_url="http://localhost:3000",
            headers={"Origin": "http://localhost:3000"},
        ) as owner,
        AsyncClient(
            transport=transport,
            base_url="http://localhost:3000",
            headers={"Origin": "http://localhost:3000"},
        ) as outsider,
    ):
        for client, name in ((owner, "owner"), (outsider, "outsider")):
            response = await client.post(
                "/api/auth/register",
                json={
                    "email": f"list-{name}-{suffix}@example.com",
                    "password": "IntentraIntegrationTest2026!",
                },
            )
            assert response.status_code == 201, response.text

        response = await owner.post(
            "/api/contracts",
            json={
                "merchant_id": f"listing-owner-{suffix}",
                "maximum_amount": "100.00",
                "currency": "USD",
            },
        )
        assert response.status_code == 201, response.text
        contract_id = response.json()["id"]

        response = await outsider.get("/api/contracts")
        assert response.status_code == 200, response.text
        assert all(
            item["id"] != contract_id
            for item in response.json()["items"]
        )

        response = await owner.get("/api/contracts?limit=1&offset=0")
        assert response.status_code == 200, response.text

        data = response.json()
        assert data["limit"] == 1
        assert data["offset"] == 0
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == contract_id

        response = await owner.get("/api/contracts?limit=101")
        assert response.status_code == 422

    async with AsyncClient(
        transport=transport,
        base_url="http://localhost:3000",
    ) as anonymous:
        response = await anonymous.get("/api/contracts")
        assert response.status_code == 401
