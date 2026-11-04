import uuid

import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import DBAPIError

from test_contract_integration import require_test_database
from test_payment_capture import approved_payment, make_registry, run_capture

from intentra.database import SessionLocal
from intentra.models.intent_contract import IntentContractRecord
from intentra.models.payment_attempt import PaymentAttemptRecord
from intentra.models.payment_attempt_event import PaymentAttemptEventRecord
from intentra.models.payment_reconciliation_event import PaymentReconciliationEventRecord
from intentra.models.payment_reservation import PaymentReservationRecord
from intentra.services.payment_capture import claim_payment_capture
from intentra.services.payment_reconciliation import PaymentReconciliationError
from intentra.services.payment_reconciliation_runner import reconcile_payment_attempt
from intentra.services.paypal_sandbox import PayPalCaptureOutcomeUnknownError


@pytest.mark.asyncio
async def test_reconcile_confirms_provider_capture_after_local_persistence_crash(monkeypatch):
    attempt_id, reservation_id, actor_id, _, _, paypal = await approved_payment()
    import intentra.services.payment_capture as capture_service
    original_event = capture_service._add_attempt_event
    def fail_after_state_mutation(db, *, attempt_id, actor_id, event_type, operation_id, data):
        if event_type == "CAPTURE_COMPLETED":
            raise RuntimeError("simulated process crash before outcome commit")
        return original_event(db, attempt_id=attempt_id, actor_id=actor_id,
            event_type=event_type, operation_id=operation_id, data=data)
    monkeypatch.setattr(capture_service, "_add_attempt_event", fail_after_state_mutation)
    with pytest.raises(RuntimeError, match="simulated process crash"):
        await run_capture(attempt_id, actor_id, paypal)
    assert paypal.capture_calls == 1
    async with SessionLocal() as db:
        attempt = await db.get(PaymentAttemptRecord, attempt_id)
        reservation = await db.get(PaymentReservationRecord, reservation_id)
    assert attempt.status == "UNKNOWN"
    assert reservation.status == "OUTCOME_UNKNOWN"
    monkeypatch.setattr(capture_service, "_add_attempt_event", original_event)
    async with SessionLocal() as db:
        result = await reconcile_payment_attempt(db, attempt_id=attempt_id,
            actor_id=actor_id, registry=make_registry(), paypal=paypal)
    async with SessionLocal() as db:
        attempt = await db.get(PaymentAttemptRecord, attempt_id)
        reservation = await db.get(PaymentReservationRecord, reservation_id)
        evidence = (await db.scalars(select(PaymentReconciliationEventRecord).where(
            PaymentReconciliationEventRecord.attempt_id == attempt_id,
        ))).all()
    assert result.action == "CAPTURE_COMPLETED"
    assert result.capture_id == paypal.capture_id
    assert attempt.status == "SUCCEEDED"
    assert attempt.capture_id == paypal.capture_id
    assert reservation.status == "CAPTURED"
    assert evidence and evidence[-1].event_type == "ORDER_VERIFIED"
    assert evidence[-1].evidence_data["reason_code"] == "CAPTURE_COMPLETED"
    assert paypal.capture_calls == 1


@pytest.mark.asyncio
async def test_reconcile_pending_or_missing_capture_keeps_budget_unknown():
    attempt_id, reservation_id, actor_id, _, _, paypal = await approved_payment()
    async with SessionLocal() as db:
        await claim_payment_capture(db, attempt_id=attempt_id,
            actor_id=actor_id, registry=make_registry())
    paypal.order_status = "APPROVED"
    paypal.capture_status = None
    async with SessionLocal() as db:
        result = await reconcile_payment_attempt(db, attempt_id=attempt_id,
            actor_id=actor_id, registry=make_registry(), paypal=paypal)
    assert result.action == "RECONCILIATION_REQUIRED"
    assert paypal.capture_calls == 0
    async with SessionLocal() as db:
        attempt = await db.get(PaymentAttemptRecord, attempt_id)
        reservation = await db.get(PaymentReservationRecord, reservation_id)
        evidence = (await db.scalars(select(PaymentReconciliationEventRecord).where(
            PaymentReconciliationEventRecord.attempt_id == attempt_id,
        ))).all()
    assert attempt.status == "UNKNOWN"
    assert reservation.status == "OUTCOME_UNKNOWN"
    assert evidence[-1].event_type == "HOLD_FOR_REVIEW"

    # A provider-reported PENDING capture remains unknown and keeps its capture ID.
    attempt2, reservation2, actor2, _, _, paypal2 = await approved_payment()
    paypal2.capture_status = "PENDING"
    assert (await run_capture(attempt2, actor2, paypal2)).state == "UNKNOWN"
    async with SessionLocal() as db:
        result2 = await reconcile_payment_attempt(db, attempt_id=attempt2,
            actor_id=actor2, registry=make_registry(), paypal=paypal2)
    async with SessionLocal() as db:
        attempt = await db.get(PaymentAttemptRecord, attempt2)
        reservation = await db.get(PaymentReservationRecord, reservation2)
    assert result2.provider_status == "PENDING"
    assert attempt.status == "UNKNOWN"
    assert reservation.status == "OUTCOME_UNKNOWN"
    assert attempt.capture_id == paypal2.capture_id


@pytest.mark.asyncio
async def test_reconcile_declined_capture_confirms_failure_without_capture_retry():
    attempt_id, reservation_id, actor_id, _, _, paypal = await approved_payment()
    paypal.capture_status = "DECLINED"
    paypal.capture_error = PayPalCaptureOutcomeUnknownError("response lost after decline")
    assert (await run_capture(attempt_id, actor_id, paypal)).state == "UNKNOWN"
    before_calls = paypal.capture_calls
    async with SessionLocal() as db:
        result = await reconcile_payment_attempt(db, attempt_id=attempt_id,
            actor_id=actor_id, registry=make_registry(), paypal=paypal)
    async with SessionLocal() as db:
        attempt = await db.get(PaymentAttemptRecord, attempt_id)
        reservation = await db.get(PaymentReservationRecord, reservation_id)
    assert result.provider_status == "DECLINED"
    assert attempt.status == "FAILED"
    assert reservation.status == "CANCELLED"
    assert paypal.capture_calls == before_calls


@pytest.mark.asyncio
async def test_reconcile_provider_failed_capture_is_terminal_failure():
    attempt_id, reservation_id, actor_id, _, _, paypal = await approved_payment()
    paypal.capture_status = "FAILED"
    paypal.capture_error = PayPalCaptureOutcomeUnknownError("capture response lost")
    assert (await run_capture(attempt_id, actor_id, paypal)).state == "UNKNOWN"
    async with SessionLocal() as db:
        result = await reconcile_payment_attempt(db, attempt_id=attempt_id,
            actor_id=actor_id, registry=make_registry(), paypal=paypal)
    async with SessionLocal() as db:
        attempt = await db.get(PaymentAttemptRecord, attempt_id)
        reservation = await db.get(PaymentReservationRecord, reservation_id)
    assert result.provider_status == "FAILED"
    assert attempt.status == "FAILED"
    assert reservation.status == "CANCELLED"


@pytest.mark.asyncio
async def test_reconciliation_auth_and_contract_change_after_capture_claim():
    attempt_id, reservation_id, actor_id, _, _, paypal = await approved_payment()
    paypal.capture_error = PayPalCaptureOutcomeUnknownError("ambiguous provider response")
    await run_capture(attempt_id, actor_id, paypal)
    with pytest.raises(PaymentReconciliationError):
        async with SessionLocal() as db:
            await reconcile_payment_attempt(db, attempt_id=attempt_id,
                actor_id=uuid.uuid4(), registry=make_registry(), paypal=paypal)

    # The capture claim linearized while authorized; a later revocation cannot
    # erase a provider-confirmed financial obligation during recovery.
    async with SessionLocal() as db:
        reservation = await db.get(PaymentReservationRecord, reservation_id)
        await db.execute(update(IntentContractRecord).where(
            IntentContractRecord.id == reservation.contract_id,
        ).values(status="REVOKED", version=IntentContractRecord.version + 1))
        await db.commit()
    paypal.capture_error = None
    paypal.order_status = "COMPLETED"
    async with SessionLocal() as db:
        result = await reconcile_payment_attempt(db, attempt_id=attempt_id,
            actor_id=actor_id, registry=make_registry(), paypal=paypal)
    assert result.action == "CAPTURE_COMPLETED"
    async with SessionLocal() as db:
        attempt = await db.get(PaymentAttemptRecord, attempt_id)
        reservation = await db.get(PaymentReservationRecord, reservation_id)
    assert attempt.status == "SUCCEEDED"
    assert reservation.status == "CAPTURED"


@pytest.mark.asyncio
async def test_reconciliation_evidence_is_immutable():
    attempt_id, _, actor_id, _, _, paypal = await approved_payment()
    paypal.capture_error = PayPalCaptureOutcomeUnknownError("unknown")
    await run_capture(attempt_id, actor_id, paypal)
    async with SessionLocal() as db:
        await reconcile_payment_attempt(db, attempt_id=attempt_id,
            actor_id=actor_id, registry=make_registry(), paypal=paypal)
    async with SessionLocal() as db:
        with pytest.raises(DBAPIError):
            await db.execute(update(PaymentReconciliationEventRecord).where(
                PaymentReconciliationEventRecord.attempt_id == attempt_id,
            ).values(event_type="HOLD_FOR_REVIEW"))
        await db.rollback()
