import asyncio
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from test_contract_integration import app, require_test_database

from intentra.database import SessionLocal
from intentra.models.payment_attempt import PaymentAttemptRecord
from intentra.services.payment_execution import claim_payment_execution
from intentra.services.payment_order_binding import (
    PaymentOrderBindingError,
    bind_provider_order,
)


async def create_claimed_attempt():
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
                "email": f"binding-{suffix}@example.com",
                "password": "IntentraIntegrationTest2026!",
            },
        )
        assert response.status_code == 201, response.text
        actor_id = uuid.UUID(response.json()["id"])

        response = await client.post(
            "/api/contracts",
            json={
                "merchant_id": "binding_test_merchant",
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
                "idempotency_key": f"binding-{suffix}",
                "merchant_id": "binding_test_merchant",
                "amount": "40.00",
                "currency": "USD",
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "RESERVED"

        reservation_id = uuid.UUID(response.json()["reservation_id"])

    async with SessionLocal() as db:
        claim = await claim_payment_execution(
            db,
            reservation_id=reservation_id,
            actor_id=actor_id,
        )

    assert claim.newly_claimed
    return claim.attempt_id


@pytest.mark.asyncio
async def test_first_order_binding_is_durable():
    attempt_id = await create_claimed_attempt()
    order_id = f"MOCK-{uuid.uuid4().hex}"

    async with SessionLocal() as db:
        result = await bind_provider_order(
            db,
            attempt_id=attempt_id,
            provider_order_id=order_id,
        )

    assert result.changed is True
    assert result.provider_order_id == order_id

    async with SessionLocal() as db:
        saved = await db.scalar(
            select(PaymentAttemptRecord).where(
                PaymentAttemptRecord.id == attempt_id
            )
        )

    assert saved is not None
    assert saved.provider_order_id == order_id


@pytest.mark.asyncio
async def test_repeated_order_binding_is_idempotent():
    attempt_id = await create_claimed_attempt()
    order_id = f"MOCK-{uuid.uuid4().hex}"

    async with SessionLocal() as db:
        first = await bind_provider_order(
            db,
            attempt_id=attempt_id,
            provider_order_id=order_id,
        )

    async with SessionLocal() as db:
        second = await bind_provider_order(
            db,
            attempt_id=attempt_id,
            provider_order_id=order_id,
        )

    assert first.changed is True
    assert second.changed is False
    assert second.provider_order_id == order_id


@pytest.mark.asyncio
async def test_conflicting_order_binding_is_rejected():
    attempt_id = await create_claimed_attempt()

    async with SessionLocal() as db:
        await bind_provider_order(
            db,
            attempt_id=attempt_id,
            provider_order_id="MOCK-ORIGINAL",
        )

    async with SessionLocal() as db:
        with pytest.raises(
            PaymentOrderBindingError,
            match="Conflicting provider order ID",
        ):
            await bind_provider_order(
                db,
                attempt_id=attempt_id,
                provider_order_id="MOCK-DIFFERENT",
            )


@pytest.mark.asyncio
async def test_concurrent_order_binding_has_one_winner():
    attempt_id = await create_claimed_attempt()

    async def bind(order_id):
        async with SessionLocal() as db:
            try:
                return await bind_provider_order(
                    db,
                    attempt_id=attempt_id,
                    provider_order_id=order_id,
                )
            except PaymentOrderBindingError as exc:
                return exc

    results = await asyncio.gather(
        bind("MOCK-WORKER-A"),
        bind("MOCK-WORKER-B"),
    )

    winners = [
        result for result in results
        if not isinstance(result, Exception)
    ]
    rejected = [
        result for result in results
        if isinstance(result, PaymentOrderBindingError)
    ]

    assert len(winners) == 1
    assert len(rejected) == 1
    assert winners[0].changed is True

    async with SessionLocal() as db:
        saved = await db.scalar(
            select(PaymentAttemptRecord).where(
                PaymentAttemptRecord.id == attempt_id
            )
        )

    assert saved is not None
    assert saved.provider_order_id == winners[0].provider_order_id
