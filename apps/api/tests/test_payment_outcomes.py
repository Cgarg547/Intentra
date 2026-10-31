import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from test_contract_integration import app, require_test_database
from intentra.database import SessionLocal
from intentra.models.payment_attempt import PaymentAttemptRecord
from intentra.models.payment_reservation import PaymentReservationRecord
from intentra.services.payment_execution import claim_payment_execution
from intentra.services.payment_outcomes import record_payment_outcome


@pytest.mark.asyncio
async def test_successful_payment_outcome_is_atomic_and_idempotent():
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
                "email": f"outcome-{suffix}@example.com",
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
                "merchant_id": "outcome_test_merchant",
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
                "idempotency_key": f"outcome-{suffix}",
                "merchant_id": "outcome_test_merchant",
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
        assert claim.newly_claimed is True

    async with SessionLocal() as db:
        result = await record_payment_outcome(
            db,
            attempt_id=claim.attempt_id,
            outcome="SUCCEEDED",
        )
        assert result.changed is True
        assert result.attempt_status == "SUCCEEDED"
        assert result.reservation_status == "CAPTURED"

    async with SessionLocal() as db:
        repeated = await record_payment_outcome(
            db,
            attempt_id=claim.attempt_id,
            outcome="SUCCEEDED",
        )
        assert repeated.changed is False
        assert repeated.attempt_status == "SUCCEEDED"
        assert repeated.reservation_status == "CAPTURED"

    async with SessionLocal() as db:
        attempt = await db.scalar(
            select(PaymentAttemptRecord).where(
                PaymentAttemptRecord.id == claim.attempt_id
            )
        )
        reservation = await db.scalar(
            select(PaymentReservationRecord).where(
                PaymentReservationRecord.id == reservation_id
            )
        )

        assert attempt.status == "SUCCEEDED"
        assert reservation.status == "CAPTURED"


@pytest.mark.asyncio
async def test_unknown_outcome_preserves_budget_until_reconciled():
    from decimal import Decimal
    from sqlalchemy import func
    from intentra.services.payment_outcomes import PaymentOutcomeError

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
                "email": f"unknown-{suffix}@example.com",
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
                "merchant_id": "unknown_test_merchant",
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
                "idempotency_key": f"unknown-{suffix}",
                "merchant_id": "unknown_test_merchant",
                "amount": "80.00",
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

    async with SessionLocal() as db:
        result = await record_payment_outcome(
            db,
            attempt_id=claim.attempt_id,
            outcome="UNKNOWN",
        )
        assert result.changed is True
        assert result.attempt_status == "UNKNOWN"
        assert result.reservation_status == "OUTCOME_UNKNOWN"

    # UNKNOWN must continue consuming the contract budget.
    async with SessionLocal() as db:
        reserved = await db.scalar(
            select(func.coalesce(func.sum(PaymentReservationRecord.amount), 0))
            .where(
                PaymentReservationRecord.contract_id == uuid.UUID(contract_id),
                PaymentReservationRecord.status.in_(
                    (
                        "RESERVED",
                        "EXECUTION_PENDING",
                        "OUTCOME_UNKNOWN",
                        "CAPTURED",
                    )
                ),
            )
        )
        assert reserved == Decimal("80.00")

    # Reconciliation can later confirm success.
    async with SessionLocal() as db:
        reconciled = await record_payment_outcome(
            db,
            attempt_id=claim.attempt_id,
            outcome="SUCCEEDED",
        )
        assert reconciled.changed is True
        assert reconciled.attempt_status == "SUCCEEDED"
        assert reconciled.reservation_status == "CAPTURED"

    # A terminal success cannot be reversed into failure.
    async with SessionLocal() as db:
        with pytest.raises(PaymentOutcomeError, match="Conflicting"):
            await record_payment_outcome(
                db,
                attempt_id=claim.attempt_id,
                outcome="FAILED",
            )

    async with SessionLocal() as db:
        attempt = await db.scalar(
            select(PaymentAttemptRecord).where(
                PaymentAttemptRecord.id == claim.attempt_id
            )
        )
        reservation = await db.scalar(
            select(PaymentReservationRecord).where(
                PaymentReservationRecord.id == reservation_id
            )
        )

        assert attempt.status == "SUCCEEDED"
        assert reservation.status == "CAPTURED"


@pytest.mark.asyncio
async def test_confirmed_failure_releases_reserved_budget():
    from decimal import Decimal
    from intentra.services.payment_outcomes import PaymentOutcomeError

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
                "email": f"failed-outcome-{suffix}@example.com",
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
                "merchant_id": "failure_test_merchant",
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
                "idempotency_key": f"failed-{suffix}",
                "merchant_id": "failure_test_merchant",
                "amount": "80.00",
                "currency": "USD",
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "RESERVED"
        reservation_id = uuid.UUID(response.json()["reservation_id"])

        # The original reservation consumes $80.
        response = await client.post(
            "/api/payments/reserve",
            json={
                "contract_id": contract_id,
                "idempotency_key": f"blocked-before-{suffix}",
                "merchant_id": "failure_test_merchant",
                "amount": "30.00",
                "currency": "USD",
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "BLOCKED"

        async with SessionLocal() as db:
            claim = await claim_payment_execution(
                db,
                reservation_id=reservation_id,
                actor_id=actor_id,
            )

        # Simulate trusted confirmation that no charge occurred.
        async with SessionLocal() as db:
            result = await record_payment_outcome(
                db,
                attempt_id=claim.attempt_id,
                outcome="FAILED",
            )
            assert result.changed is True
            assert result.attempt_status == "FAILED"
            assert result.reservation_status == "CANCELLED"

        # A different idempotency key can now reserve the freed budget.
        response = await client.post(
            "/api/payments/reserve",
            json={
                "contract_id": contract_id,
                "idempotency_key": f"after-failure-{suffix}",
                "merchant_id": "failure_test_merchant",
                "amount": "100.00",
                "currency": "USD",
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "RESERVED"
        assert Decimal(response.json()["remaining_amount"]) == Decimal("0.00")

    # A terminal failure cannot later be changed into success.
    async with SessionLocal() as db:
        with pytest.raises(PaymentOutcomeError, match="Conflicting"):
            await record_payment_outcome(
                db,
                attempt_id=claim.attempt_id,
                outcome="SUCCEEDED",
            )

    async with SessionLocal() as db:
        attempt = await db.scalar(
            select(PaymentAttemptRecord).where(
                PaymentAttemptRecord.id == claim.attempt_id
            )
        )
        reservation = await db.scalar(
            select(PaymentReservationRecord).where(
                PaymentReservationRecord.id == reservation_id
            )
        )

        assert attempt.status == "FAILED"
        assert reservation.status == "CANCELLED"


@pytest.mark.asyncio
async def test_concurrent_conflicting_outcomes_cannot_both_commit():
    import asyncio

    from intentra.services.payment_outcomes import PaymentOutcomeError

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
                "email": f"conflict-{suffix}@example.com",
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
                "merchant_id": "conflict_test_merchant",
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
                "idempotency_key": f"conflict-{suffix}",
                "merchant_id": "conflict_test_merchant",
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

    async def report(outcome):
        async with SessionLocal() as db:
            return await record_payment_outcome(
                db,
                attempt_id=claim.attempt_id,
                outcome=outcome,
            )

    results = await asyncio.gather(
        report("SUCCEEDED"),
        report("FAILED"),
        return_exceptions=True,
    )

    successful = [
        result for result in results
        if not isinstance(result, BaseException)
    ]
    rejected = [
        result for result in results
        if isinstance(result, PaymentOutcomeError)
    ]

    assert len(successful) == 1, results
    assert len(rejected) == 1, results
    assert successful[0].changed is True

    async with SessionLocal() as db:
        attempt = await db.scalar(
            select(PaymentAttemptRecord).where(
                PaymentAttemptRecord.id == claim.attempt_id
            )
        )
        reservation = await db.scalar(
            select(PaymentReservationRecord).where(
                PaymentReservationRecord.id == reservation_id
            )
        )

        assert attempt.status in {"SUCCEEDED", "FAILED"}

        expected_reservation = {
            "SUCCEEDED": "CAPTURED",
            "FAILED": "CANCELLED",
        }[attempt.status]

        assert reservation.status == expected_reservation
