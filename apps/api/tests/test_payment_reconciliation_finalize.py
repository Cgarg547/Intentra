import uuid

import pytest
from sqlalchemy import select

from tests.test_contract_integration import require_test_database
from tests.test_payment_order_binding import create_claimed_attempt

from intentra.database import SessionLocal
from intentra.models.payment_attempt import PaymentAttemptRecord
from intentra.models.payment_reservation import PaymentReservationRecord
from intentra.models.payment_reconciliation_event import (
    PaymentReconciliationEventRecord,
)
from intentra.services.payment_reconciliation_finalize import (
    ReconciliationFinalizeError,
    finalize_reconciliation_evidence,
)


async def payment_snapshot(attempt_id):
    async with SessionLocal() as db:
        attempt = await db.get(PaymentAttemptRecord, attempt_id)
        reservation = await db.get(
            PaymentReservationRecord,
            attempt.reservation_id,
        )

        return (
            attempt.id,
            attempt.reservation_id,
            attempt.status,
            attempt.provider_order_id,
            reservation.contract_id,
            reservation.contract_version,
            reservation.status,
            reservation.merchant_id,
            reservation.amount,
            reservation.currency,
        )


async def evidence_for(operation_id):
    async with SessionLocal() as db:
        return await db.scalar(
            select(PaymentReconciliationEventRecord).where(
                PaymentReconciliationEventRecord.operation_id
                == operation_id
            )
        )


@pytest.mark.asyncio
async def test_finalization_persists_evidence_without_payment_change():
    require_test_database()
    attempt_id = await create_claimed_attempt()
    snapshot = await payment_snapshot(attempt_id)
    operation_id = uuid.uuid4()

    async with SessionLocal() as db:
        result = await finalize_reconciliation_evidence(
            db,
            operation_id=operation_id,
            attempt_id=attempt_id,
            expected_snapshot=snapshot,
            event_type="HOLD_FOR_REVIEW",
            provider_order_id=None,
            provider_status=None,
            evidence_data={"reason_code": "ORDER_ID_UNKNOWN"},
        )

    assert result.created is True

    event = await evidence_for(operation_id)
    assert event is not None
    assert event.attempt_id == attempt_id
    assert event.event_type == "HOLD_FOR_REVIEW"
    assert event.evidence_data == {
        "reason_code": "ORDER_ID_UNKNOWN"
    }

    assert await payment_snapshot(attempt_id) == snapshot


@pytest.mark.asyncio
async def test_finalization_rejects_stale_reservation_state():
    require_test_database()
    attempt_id = await create_claimed_attempt()
    snapshot = await payment_snapshot(attempt_id)
    operation_id = uuid.uuid4()

    async with SessionLocal() as db:
        async with db.begin():
            reservation = await db.get(
                PaymentReservationRecord,
                snapshot[1],
            )
            reservation.amount += 1

    async with SessionLocal() as db:
        with pytest.raises(
            ReconciliationFinalizeError,
            match="Payment state changed",
        ):
            await finalize_reconciliation_evidence(
                db,
                operation_id=operation_id,
                attempt_id=attempt_id,
                expected_snapshot=snapshot,
                event_type="ORDER_VERIFIED",
                provider_order_id="MOCK-ORDER",
                provider_status="CREATED",
                evidence_data={
                    "reason_code": "ORDER_ID_VERIFIED"
                },
            )

    assert await evidence_for(operation_id) is None


@pytest.mark.asyncio
async def test_finalization_rejects_stale_attempt_state():
    require_test_database()
    attempt_id = await create_claimed_attempt()
    snapshot = await payment_snapshot(attempt_id)
    operation_id = uuid.uuid4()

    async with SessionLocal() as db:
        async with db.begin():
            attempt = await db.get(
                PaymentAttemptRecord,
                attempt_id,
            )
            attempt.status = "UNKNOWN"

    async with SessionLocal() as db:
        with pytest.raises(
            ReconciliationFinalizeError,
            match="Payment state changed",
        ):
            await finalize_reconciliation_evidence(
                db,
                operation_id=operation_id,
                attempt_id=attempt_id,
                expected_snapshot=snapshot,
                event_type="ORDER_VERIFIED",
                provider_order_id="MOCK-ORDER",
                provider_status="CREATED",
                evidence_data={
                    "reason_code": "ORDER_ID_VERIFIED"
                },
            )

    assert await evidence_for(operation_id) is None


@pytest.mark.asyncio
async def test_finalization_identical_retry_is_idempotent():
    require_test_database()
    attempt_id = await create_claimed_attempt()
    snapshot = await payment_snapshot(attempt_id)
    operation_id = uuid.uuid4()

    kwargs = {
        "operation_id": operation_id,
        "attempt_id": attempt_id,
        "expected_snapshot": snapshot,
        "event_type": "HOLD_FOR_REVIEW",
        "provider_order_id": None,
        "provider_status": None,
        "evidence_data": {
            "reason_code": "ORDER_ID_UNKNOWN"
        },
    }

    async with SessionLocal() as db:
        first = await finalize_reconciliation_evidence(
            db, **kwargs
        )

    async with SessionLocal() as db:
        second = await finalize_reconciliation_evidence(
            db, **kwargs
        )

    assert first.created is True
    assert second.created is False
    assert first.event_id == second.event_id


@pytest.mark.asyncio
async def test_finalization_rejects_conflicting_operation_retry():
    from intentra.services.payment_reconciliation_evidence import (
        ReconciliationEvidenceError,
    )

    require_test_database()
    attempt_id = await create_claimed_attempt()
    snapshot = await payment_snapshot(attempt_id)
    operation_id = uuid.uuid4()

    async with SessionLocal() as db:
        await finalize_reconciliation_evidence(
            db,
            operation_id=operation_id,
            attempt_id=attempt_id,
            expected_snapshot=snapshot,
            event_type="HOLD_FOR_REVIEW",
            provider_order_id=None,
            provider_status=None,
            evidence_data={"reason_code": "ORDER_ID_UNKNOWN"},
        )

    async with SessionLocal() as db:
        with pytest.raises(
            ReconciliationEvidenceError,
            match="Conflicting reconciliation evidence",
        ):
            await finalize_reconciliation_evidence(
                db,
                operation_id=operation_id,
                attempt_id=attempt_id,
                expected_snapshot=snapshot,
                event_type="ORDER_VERIFIED",
                provider_order_id="MOCK-ORDER",
                provider_status="CREATED",
                evidence_data={
                    "reason_code": "ORDER_ID_VERIFIED"
                },
            )

    event = await evidence_for(operation_id)
    assert event.event_type == "HOLD_FOR_REVIEW"


@pytest.mark.asyncio
async def test_concurrent_finalization_creates_one_evidence_event():
    import asyncio

    require_test_database()
    attempt_id = await create_claimed_attempt()
    snapshot = await payment_snapshot(attempt_id)
    operation_id = uuid.uuid4()

    async def finalize_once():
        async with SessionLocal() as db:
            return await finalize_reconciliation_evidence(
                db,
                operation_id=operation_id,
                attempt_id=attempt_id,
                expected_snapshot=snapshot,
                event_type="HOLD_FOR_REVIEW",
                provider_order_id=None,
                provider_status=None,
                evidence_data={
                    "reason_code": "ORDER_ID_UNKNOWN"
                },
            )

    first, second = await asyncio.wait_for(
        asyncio.gather(finalize_once(), finalize_once()),
        timeout=15,
    )

    assert first.event_id == second.event_id
    assert sorted([first.created, second.created]) == [
        False,
        True,
    ]

    event = await evidence_for(operation_id)
    assert event is not None
    assert event.event_type == "HOLD_FOR_REVIEW"

    assert await payment_snapshot(attempt_id) == snapshot
