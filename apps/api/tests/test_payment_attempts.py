import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from test_contract_integration import app, require_test_database

from httpx import ASGITransport, AsyncClient

from intentra.database import SessionLocal
from intentra.models.payment_attempt import PaymentAttemptRecord


@pytest.mark.asyncio
async def test_payment_attempt_is_durable_and_unique():
    require_test_database()

    suffix = uuid.uuid4().hex

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://localhost:3000",
        headers={"Origin": "http://localhost:3000"},
    ) as client:
        response = await client.post(
            "/api/auth/register",
            json={
                "email": f"attempt-{suffix}@example.com",
                "password": "IntentraIntegrationTest2026!",
            },
        )
        assert response.status_code == 201, response.text

        response = await client.post(
            "/api/contracts",
            json={
                "merchant_id": "attempt_test_merchant",
                "maximum_amount": "100.00",
                "currency": "USD",
            },
        )
        assert response.status_code == 201, response.text
        contract_id = response.json()["id"]

        response = await client.post(
            f"/api/contracts/{contract_id}/approve",
            json={"expected_version": 1},
        )
        assert response.status_code == 200, response.text

        response = await client.post(
            "/api/payments/reserve",
            json={
                "contract_id": contract_id,
                "idempotency_key": f"reserve-{suffix}",
                "merchant_id": "attempt_test_merchant",
                "amount": "40.00",
                "currency": "USD",
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "RESERVED"

        reservation_id = uuid.UUID(response.json()["reservation_id"])

    provider_key = f"provider-{suffix}"

    async with SessionLocal() as db:
        attempt = PaymentAttemptRecord(
            reservation_id=reservation_id,
            provider_idempotency_key=provider_key,
            status="PENDING",
        )
        db.add(attempt)
        await db.commit()
        attempt_id = attempt.id

    # Verify persistence across database sessions.
    async with SessionLocal() as db:
        saved = await db.scalar(
            select(PaymentAttemptRecord).where(
                PaymentAttemptRecord.id == attempt_id
            )
        )
        assert saved is not None
        assert saved.reservation_id == reservation_id
        assert saved.provider_idempotency_key == provider_key
        assert saved.status == "PENDING"

    # The same reservation cannot receive another attempt.
    async with SessionLocal() as db:
        db.add(
            PaymentAttemptRecord(
                reservation_id=reservation_id,
                provider_idempotency_key=f"second-{suffix}",
                status="PENDING",
            )
        )
        with pytest.raises(IntegrityError):
            await db.commit()
        await db.rollback()

    # A provider idempotency key cannot be reused.
    async with SessionLocal() as db:
        db.add(
            PaymentAttemptRecord(
                reservation_id=reservation_id,
                provider_idempotency_key=provider_key,
                status="PENDING",
            )
        )
        with pytest.raises(IntegrityError):
            await db.commit()
        await db.rollback()
