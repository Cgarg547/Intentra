import asyncio
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from test_contract_integration import app, require_test_database
from intentra.database import SessionLocal
from intentra.models.payment_attempt import PaymentAttemptRecord
from intentra.models.payment_reservation import PaymentReservationRecord
from intentra.services.payment_execution import (
    claim_payment_execution,
)


@pytest.mark.asyncio
async def test_concurrent_execution_claims_create_one_attempt():
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
                "email": f"execution-{suffix}@example.com",
                "password": "IntentraIntegrationTest2026!",
            },
        )
        assert response.status_code == 201, response.text

        response = await client.get("/api/auth/me")
        assert response.status_code == 200, response.text
        actor_id = uuid.UUID(response.json()["id"])

        response = await client.post(
            "/api/contracts",
            json={
                "merchant_id": "execution_test_merchant",
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
                "idempotency_key": f"execution-{suffix}",
                "merchant_id": "execution_test_merchant",
                "amount": "40.00",
                "currency": "USD",
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "RESERVED"

        reservation_id = uuid.UUID(response.json()["reservation_id"])

    async def claim():
        async with SessionLocal() as db:
            return await claim_payment_execution(
                db,
                reservation_id=reservation_id,
                actor_id=actor_id,
            )

    results = await asyncio.gather(
        *[claim() for _ in range(10)]
    )

    assert len({result.attempt_id for result in results}) == 1
    assert len({result.provider_idempotency_key for result in results}) == 1
    assert sum(result.newly_claimed for result in results) == 1

    async with SessionLocal() as db:
        attempts = await db.scalar(
            select(func.count())
            .select_from(PaymentAttemptRecord)
            .where(PaymentAttemptRecord.reservation_id == reservation_id)
        )

        reservation = await db.scalar(
            select(PaymentReservationRecord).where(
                PaymentReservationRecord.id == reservation_id
            )
        )

        assert attempts == 1
        assert reservation.status == "EXECUTION_PENDING"


@pytest.mark.asyncio
async def test_revoked_contract_cannot_start_execution():
    from intentra.services.payment_execution import ExecutionClaimError

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
                "email": f"revoked-execution-{suffix}@example.com",
                "password": "IntentraIntegrationTest2026!",
            },
        )
        assert response.status_code == 201, response.text

        response = await client.get("/api/auth/me")
        assert response.status_code == 200, response.text
        actor_id = uuid.UUID(response.json()["id"])

        response = await client.post(
            "/api/contracts",
            json={
                "merchant_id": "revocation_test_merchant",
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
                "idempotency_key": f"revocation-{suffix}",
                "merchant_id": "revocation_test_merchant",
                "amount": "40.00",
                "currency": "USD",
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "RESERVED"
        reservation_id = uuid.UUID(response.json()["reservation_id"])

        response = await client.post(
            f"/api/contracts/{contract_id}/revoke",
            json={"expected_version": 2},
        )
        assert response.status_code == 200, response.text

    async with SessionLocal() as db:
        with pytest.raises(ExecutionClaimError):
            await claim_payment_execution(
                db,
                reservation_id=reservation_id,
                actor_id=actor_id,
            )

    async with SessionLocal() as db:
        reservation = await db.scalar(
            select(PaymentReservationRecord).where(
                PaymentReservationRecord.id == reservation_id
            )
        )
        attempt_count = await db.scalar(
            select(func.count())
            .select_from(PaymentAttemptRecord)
            .where(PaymentAttemptRecord.reservation_id == reservation_id)
        )

        assert reservation.status == "RESERVED"
        assert attempt_count == 0


@pytest.mark.asyncio
async def test_cancelled_reservation_cannot_start_execution():
    from intentra.services.payment_execution import ExecutionClaimError

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
                "email": f"cancel-execution-{suffix}@example.com",
                "password": "IntentraIntegrationTest2026!",
            },
        )
        assert response.status_code == 201, response.text

        response = await client.get("/api/auth/me")
        assert response.status_code == 200, response.text
        actor_id = uuid.UUID(response.json()["id"])

        response = await client.post(
            "/api/contracts",
            json={
                "merchant_id": "cancellation_test_merchant",
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
                "idempotency_key": f"cancel-{suffix}",
                "merchant_id": "cancellation_test_merchant",
                "amount": "40.00",
                "currency": "USD",
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "RESERVED"
        reservation_id = uuid.UUID(response.json()["reservation_id"])

    # Test setup only: simulate a cancellation in the database.
    # No public cancellation endpoint exists yet.
    async with SessionLocal() as db:
        reservation = await db.scalar(
            select(PaymentReservationRecord)
            .where(PaymentReservationRecord.id == reservation_id)
            .with_for_update()
        )
        assert reservation is not None
        reservation.status = "CANCELLED"
        reservation.reason = "Cancelled during integration test."
        await db.commit()

    async with SessionLocal() as db:
        with pytest.raises(ExecutionClaimError, match="not executable"):
            await claim_payment_execution(
                db,
                reservation_id=reservation_id,
                actor_id=actor_id,
            )

    async with SessionLocal() as db:
        reservation = await db.scalar(
            select(PaymentReservationRecord).where(
                PaymentReservationRecord.id == reservation_id
            )
        )
        attempt_count = await db.scalar(
            select(func.count())
            .select_from(PaymentAttemptRecord)
            .where(PaymentAttemptRecord.reservation_id == reservation_id)
        )

        assert reservation.status == "CANCELLED"
        assert attempt_count == 0


@pytest.mark.asyncio
async def test_stale_contract_version_cannot_start_execution():
    from intentra.services.payment_execution import ExecutionClaimError
    from intentra.models.intent_contract import IntentContractRecord

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
                "email": f"stale-execution-{suffix}@example.com",
                "password": "IntentraIntegrationTest2026!",
            },
        )
        assert response.status_code == 201, response.text

        response = await client.get("/api/auth/me")
        assert response.status_code == 200, response.text
        actor_id = uuid.UUID(response.json()["id"])

        response = await client.post(
            "/api/contracts",
            json={
                "merchant_id": "stale_test_merchant",
                "maximum_amount": "100.00",
                "currency": "USD",
            },
        )
        assert response.status_code == 201, response.text
        contract_id = uuid.UUID(response.json()["id"])

        response = await client.post(
            f"/api/contracts/{contract_id}/approve",
            json={"expected_version": 1},
        )
        assert response.status_code == 200, response.text

        response = await client.post(
            "/api/payments/reserve",
            json={
                "contract_id": str(contract_id),
                "idempotency_key": f"stale-{suffix}",
                "merchant_id": "stale_test_merchant",
                "amount": "40.00",
                "currency": "USD",
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "RESERVED"
        reservation_id = uuid.UUID(response.json()["reservation_id"])

    # Test setup only: simulate a later approved contract version.
    async with SessionLocal() as db:
        contract = await db.scalar(
            select(IntentContractRecord)
            .where(IntentContractRecord.id == contract_id)
            .with_for_update()
        )
        assert contract is not None
        assert contract.status == "APPROVED"
        contract.version += 1
        await db.commit()

    async with SessionLocal() as db:
        with pytest.raises(ExecutionClaimError, match="version is stale"):
            await claim_payment_execution(
                db,
                reservation_id=reservation_id,
                actor_id=actor_id,
            )

    async with SessionLocal() as db:
        reservation = await db.scalar(
            select(PaymentReservationRecord).where(
                PaymentReservationRecord.id == reservation_id
            )
        )
        attempt_count = await db.scalar(
            select(func.count())
            .select_from(PaymentAttemptRecord)
            .where(PaymentAttemptRecord.reservation_id == reservation_id)
        )

        assert reservation.status == "RESERVED"
        assert attempt_count == 0


@pytest.mark.asyncio
async def test_execution_claim_failure_rolls_back_reservation():
    from sqlalchemy.exc import IntegrityError
    from intentra.models.payment_attempt import PaymentAttemptRecord
    from intentra.services.payment_execution import ExecutionClaimError

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
                "email": f"rollback-{suffix}@example.com",
                "password": "IntentraIntegrationTest2026!",
            },
        )
        assert response.status_code == 201, response.text

        response = await client.get("/api/auth/me")
        assert response.status_code == 200, response.text
        actor_id = uuid.UUID(response.json()["id"])

        response = await client.post(
            "/api/contracts",
            json={
                "merchant_id": "rollback_test_merchant",
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

        reservation_ids = []
        for index in range(2):
            response = await client.post(
                "/api/payments/reserve",
                json={
                    "contract_id": contract_id,
                    "idempotency_key": f"rollback-{suffix}-{index}",
                    "merchant_id": "rollback_test_merchant",
                    "amount": "40.00",
                    "currency": "USD",
                },
            )
            assert response.status_code == 200, response.text
            assert response.json()["status"] == "RESERVED"
            reservation_ids.append(
                uuid.UUID(response.json()["reservation_id"])
            )

    first_id, second_id = reservation_ids

    # Deliberately occupy the provider key that the second
    # reservation will use. This forces a unique-constraint
    # failure when the second execution claim is flushed.
    async with SessionLocal() as db:
        db.add(
            PaymentAttemptRecord(
                reservation_id=first_id,
                provider_idempotency_key=f"intentra-{second_id}",
                status="PENDING",
            )
        )
        await db.commit()

    async with SessionLocal() as db:
        with pytest.raises(IntegrityError):
            await claim_payment_execution(
                db,
                reservation_id=second_id,
                actor_id=actor_id,
            )
        await db.rollback()

    # The failed INSERT must roll back the reservation UPDATE.
    async with SessionLocal() as db:
        reservation = await db.scalar(
            select(PaymentReservationRecord).where(
                PaymentReservationRecord.id == second_id
            )
        )
        attempt_count = await db.scalar(
            select(func.count())
            .select_from(PaymentAttemptRecord)
            .where(PaymentAttemptRecord.reservation_id == second_id)
        )

        assert reservation.status == "RESERVED"
        assert attempt_count == 0
