import uuid

import pytest
from sqlalchemy import select

from tests.test_contract_integration import require_test_database
from tests.test_payment_order_binding import create_claimed_attempt

from intentra.database import SessionLocal
from intentra.models.payment_reconciliation_event import (
    PaymentReconciliationEventRecord,
)
from intentra.services.payment_reconciliation_evidence import (
    ReconciliationEvidenceError,
    record_reconciliation_evidence,
)


@pytest.mark.asyncio
async def test_evidence_persists_without_payment_state_change():
    require_test_database()
    attempt_id = await create_claimed_attempt()
    operation_id = uuid.uuid4()

    async with SessionLocal() as db:
        async with db.begin():
            result = await record_reconciliation_evidence(
                db,
                operation_id=operation_id,
                attempt_id=attempt_id,
                event_type="HOLD_FOR_REVIEW",
                evidence_data={"reason_code": "ORDER_ID_UNKNOWN"},
            )

    assert result.created is True

    async with SessionLocal() as db:
        event = await db.scalar(
            select(PaymentReconciliationEventRecord).where(
                PaymentReconciliationEventRecord.operation_id
                == operation_id
            )
        )

    assert event is not None
    assert event.attempt_id == attempt_id
    assert event.event_type == "HOLD_FOR_REVIEW"
    assert event.evidence_data == {
        "reason_code": "ORDER_ID_UNKNOWN"
    }


@pytest.mark.asyncio
async def test_identical_operation_retry_is_idempotent():
    require_test_database()
    attempt_id = await create_claimed_attempt()
    operation_id = uuid.uuid4()

    kwargs = {
        "operation_id": operation_id,
        "attempt_id": attempt_id,
        "event_type": "HOLD_FOR_REVIEW",
        "evidence_data": {"reason_code": "ORDER_ID_UNKNOWN"},
    }

    async with SessionLocal() as db:
        async with db.begin():
            first = await record_reconciliation_evidence(
                db, **kwargs
            )

    async with SessionLocal() as db:
        async with db.begin():
            second = await record_reconciliation_evidence(
                db, **kwargs
            )

    assert first.created is True
    assert second.created is False
    assert first.event_id == second.event_id


@pytest.mark.asyncio
async def test_conflicting_operation_retry_is_rejected():
    require_test_database()
    attempt_id = await create_claimed_attempt()
    operation_id = uuid.uuid4()

    async with SessionLocal() as db:
        async with db.begin():
            await record_reconciliation_evidence(
                db,
                operation_id=operation_id,
                attempt_id=attempt_id,
                event_type="HOLD_FOR_REVIEW",
                evidence_data={"reason_code": "ORDER_ID_UNKNOWN"},
            )

    async with SessionLocal() as db:
        with pytest.raises(
            ReconciliationEvidenceError,
            match="Conflicting reconciliation evidence",
        ):
            async with db.begin():
                await record_reconciliation_evidence(
                    db,
                    operation_id=operation_id,
                    attempt_id=attempt_id,
                    event_type="ORDER_VERIFIED",
                    provider_order_id="MOCK-ORDER",
                    evidence_data={
                        "reason_code": "ORDER_ID_VERIFIED"
                    },
                )


@pytest.mark.asyncio
async def test_rejects_unapproved_evidence_fields():
    require_test_database()
    attempt_id = await create_claimed_attempt()

    async with SessionLocal() as db:
        with pytest.raises(
            ReconciliationEvidenceError,
            match="unsupported fields",
        ):
            async with db.begin():
                await record_reconciliation_evidence(
                    db,
                    operation_id=uuid.uuid4(),
                    attempt_id=attempt_id,
                    event_type="LOOKUP_FAILED",
                    evidence_data={
                        "access_token": "must-not-be-stored"
                    },
                )


@pytest.mark.asyncio
async def test_concurrent_identical_writes_create_one_event():
    import asyncio

    require_test_database()
    attempt_id = await create_claimed_attempt()
    operation_id = uuid.uuid4()

    async def write_once():
        async with SessionLocal() as db:
            async with db.begin():
                return await record_reconciliation_evidence(
                    db,
                    operation_id=operation_id,
                    attempt_id=attempt_id,
                    event_type="HOLD_FOR_REVIEW",
                    evidence_data={
                        "reason_code": "ORDER_ID_UNKNOWN",
                    },
                )

    first, second = await asyncio.wait_for(
        asyncio.gather(write_once(), write_once()),
        timeout=15,
    )

    assert first.event_id == second.event_id
    assert sorted([first.created, second.created]) == [
        False,
        True,
    ]

    async with SessionLocal() as db:
        events = (
            await db.scalars(
                select(PaymentReconciliationEventRecord).where(
                    PaymentReconciliationEventRecord.operation_id
                    == operation_id
                )
            )
        ).all()

    assert len(events) == 1


@pytest.mark.asyncio
async def test_rolled_back_evidence_is_not_persisted():
    require_test_database()
    attempt_id = await create_claimed_attempt()
    operation_id = uuid.uuid4()

    with pytest.raises(RuntimeError, match="Force rollback"):
        async with SessionLocal() as db:
            async with db.begin():
                await record_reconciliation_evidence(
                    db,
                    operation_id=operation_id,
                    attempt_id=attempt_id,
                    event_type="HOLD_FOR_REVIEW",
                    evidence_data={
                        "reason_code": "ORDER_ID_UNKNOWN",
                    },
                )
                raise RuntimeError("Force rollback")

    async with SessionLocal() as db:
        event = await db.scalar(
            select(PaymentReconciliationEventRecord).where(
                PaymentReconciliationEventRecord.operation_id
                == operation_id
            )
        )

    assert event is None


@pytest.mark.asyncio
async def test_evidence_write_preserves_payment_state():
    from intentra.models.payment_attempt import PaymentAttemptRecord
    from intentra.models.payment_reservation import (
        PaymentReservationRecord,
    )

    require_test_database()
    attempt_id = await create_claimed_attempt()

    async with SessionLocal() as db:
        attempt = await db.get(PaymentAttemptRecord, attempt_id)
        reservation = await db.get(
            PaymentReservationRecord,
            attempt.reservation_id,
        )

        original = (
            attempt.status,
            attempt.provider_order_id,
            reservation.status,
            reservation.amount,
            reservation.reason,
        )

    async with SessionLocal() as db:
        async with db.begin():
            await record_reconciliation_evidence(
                db,
                operation_id=uuid.uuid4(),
                attempt_id=attempt_id,
                event_type="HOLD_FOR_REVIEW",
                evidence_data={
                    "reason_code": "ORDER_ID_UNKNOWN",
                },
            )

    async with SessionLocal() as db:
        attempt = await db.get(PaymentAttemptRecord, attempt_id)
        reservation = await db.get(
            PaymentReservationRecord,
            attempt.reservation_id,
        )

        current = (
            attempt.status,
            attempt.provider_order_id,
            reservation.status,
            reservation.amount,
            reservation.reason,
        )

    assert current == original


@pytest.mark.asyncio
async def test_database_rejects_evidence_update():
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    require_test_database()
    attempt_id = await create_claimed_attempt()
    operation_id = uuid.uuid4()

    async with SessionLocal() as db:
        async with db.begin():
            await record_reconciliation_evidence(
                db,
                operation_id=operation_id,
                attempt_id=attempt_id,
                event_type="HOLD_FOR_REVIEW",
                evidence_data={"reason_code": "ORDER_ID_UNKNOWN"},
            )

    async with SessionLocal() as db:
        with pytest.raises(DBAPIError, match="append-only"):
            async with db.begin():
                await db.execute(
                    text("""
                        UPDATE payment_reconciliation_events
                        SET event_type = 'ORDER_VERIFIED'
                        WHERE operation_id = :operation_id
                    """),
                    {"operation_id": operation_id},
                )

    async with SessionLocal() as db:
        event = await db.scalar(
            select(PaymentReconciliationEventRecord).where(
                PaymentReconciliationEventRecord.operation_id
                == operation_id
            )
        )

    assert event.event_type == "HOLD_FOR_REVIEW"


@pytest.mark.asyncio
async def test_database_rejects_evidence_delete():
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    require_test_database()
    attempt_id = await create_claimed_attempt()
    operation_id = uuid.uuid4()

    async with SessionLocal() as db:
        async with db.begin():
            await record_reconciliation_evidence(
                db,
                operation_id=operation_id,
                attempt_id=attempt_id,
                event_type="HOLD_FOR_REVIEW",
                evidence_data={"reason_code": "ORDER_ID_UNKNOWN"},
            )

    async with SessionLocal() as db:
        with pytest.raises(DBAPIError, match="append-only"):
            async with db.begin():
                await db.execute(
                    text("""
                        DELETE FROM payment_reconciliation_events
                        WHERE operation_id = :operation_id
                    """),
                    {"operation_id": operation_id},
                )

    async with SessionLocal() as db:
        event = await db.scalar(
            select(PaymentReconciliationEventRecord).where(
                PaymentReconciliationEventRecord.operation_id
                == operation_id
            )
        )

    assert event is not None
