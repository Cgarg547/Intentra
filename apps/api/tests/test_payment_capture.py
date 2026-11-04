import asyncio
import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select, update

from test_contract_integration import require_test_database
from test_payment_order_binding import create_claimed_attempt

from intentra.database import SessionLocal
from intentra.models.intent_contract import IntentContractRecord
from intentra.models.payment_attempt import PaymentAttemptRecord
from intentra.models.payment_attempt_event import PaymentAttemptEventRecord
from intentra.models.payment_checkout_approval import PaymentCheckoutApprovalRecord
from intentra.models.payment_reservation import PaymentReservationRecord
from intentra.services.checkout_approval import initiate_checkout_approval, verify_checkout_return
from intentra.services.merchant_registry import TrustedMerchantRegistry
from intentra.services.payment_capture import PaymentCaptureError, capture_approved_payment, claim_payment_capture
from intentra.services.payment_order_binding import bind_provider_order
from intentra.services.paypal_sandbox import (
    PayPalCaptureNotSubmittedError,
    PayPalCaptureOutcomeUnknownError,
)


PAYPAL_MERCHANT = "PAYPAL-MERCHANT"


def make_registry():
    return TrustedMerchantRegistry({"binding_test_merchant": PAYPAL_MERCHANT})


class MockPayPal:
    def __init__(self, order_id):
        self.order_id = order_id
        self.order_status = "CREATED"
        self.capture_status = "COMPLETED"
        self.capture_id = f"CAP-{uuid.uuid4().hex}"
        self.capture_error = None
        self.capture_response = None
        self.gate = None
        self.capture_calls = 0
        self.capture_keys = []
        self.captured_order_ids = []

    def _order(self, include_capture=False):
        unit = {
            "payee": {"merchant_id": PAYPAL_MERCHANT},
            "amount": {"currency_code": "USD", "value": "40.00"},
        }
        if include_capture:
            unit["payments"] = {"captures": [{
                "id": self.capture_id,
                "status": self.capture_status,
                "amount": {"currency_code": "USD", "value": "40.00"},
            }]}
        return {"id": self.order_id, "status": self.order_status, "purchase_units": [unit]}

    async def get_order(self, *, order_id, expected_paypal_merchant_id, amount, currency):
        assert order_id == self.order_id
        assert expected_paypal_merchant_id == PAYPAL_MERCHANT
        assert amount == Decimal("40.00") and currency == "USD"
        return self._order(include_capture=self.capture_calls > 0 and self.capture_status is not None)

    async def capture_order(self, *, order_id, expected_paypal_merchant_id, amount, currency, provider_idempotency_key):
        self.capture_calls += 1
        self.capture_keys.append(provider_idempotency_key)
        self.captured_order_ids.append(order_id)
        if self.gate is not None:
            await self.gate.wait()
        if self.capture_error is not None:
            raise self.capture_error
        if self.capture_response is not None:
            return self.capture_response
        self.order_status = "COMPLETED" if self.capture_status == "COMPLETED" else self.capture_status
        return self._order(include_capture=True)


async def approved_payment(lifetime=None):
    require_test_database()
    attempt_id = await create_claimed_attempt()
    order_id = f"MOCK-CAPTURE-{uuid.uuid4().hex}"
    async with SessionLocal() as db:
        attempt = await db.get(PaymentAttemptRecord, attempt_id)
        reservation = await db.get(PaymentReservationRecord, attempt.reservation_id)
        actor_id = reservation.actor_id
        create_key = attempt.provider_idempotency_key
        reservation_id = reservation.id
        await bind_provider_order(db, attempt_id=attempt_id, provider_order_id=order_id)

    paypal = MockPayPal(order_id)
    async with SessionLocal() as db:
        args = {}
        if lifetime is not None:
            args["lifetime"] = lifetime
        handoff = await initiate_checkout_approval(db, attempt_id=attempt_id,
            actor_id=actor_id, registry=make_registry(), paypal=paypal, **args)
    paypal.order_status = "APPROVED"
    async with SessionLocal() as db:
        await verify_checkout_return(db, attempt_id=attempt_id, actor_id=actor_id,
            return_state=handoff.return_state, registry=make_registry(), paypal=paypal)
    return attempt_id, reservation_id, actor_id, create_key, handoff, paypal


async def run_capture(attempt_id, actor_id, paypal):
    async with SessionLocal() as db:
        return await capture_approved_payment(db, attempt_id=attempt_id,
            actor_id=actor_id, registry=make_registry(), paypal=paypal)


@pytest.mark.asyncio
async def test_verified_approval_capture_persists_capture_and_distinct_key():
    attempt_id, reservation_id, actor_id, order_key, _, paypal = await approved_payment()
    result = await run_capture(attempt_id, actor_id, paypal)
    assert result.state == "SUCCEEDED"
    assert result.action == "CAPTURE_COMPLETED"
    assert result.capture_id == paypal.capture_id
    assert paypal.capture_calls == 1
    assert paypal.captured_order_ids == [paypal.order_id]
    assert paypal.capture_keys[0] != order_key

    async with SessionLocal() as db:
        attempt = await db.get(PaymentAttemptRecord, attempt_id)
        reservation = await db.get(PaymentReservationRecord, reservation_id)
        events = (await db.scalars(select(PaymentAttemptEventRecord).where(
            PaymentAttemptEventRecord.attempt_id == attempt_id,
        ))).all()
    assert attempt.status == "SUCCEEDED"
    assert attempt.capture_id == paypal.capture_id
    assert attempt.capture_idempotency_key == paypal.capture_keys[0]
    assert attempt.capture_claimed_at is not None
    assert attempt.capture_idempotency_key != attempt.provider_idempotency_key
    assert reservation.status == "CAPTURED"
    assert any(event.event_type == "CAPTURE_CLAIMED" for event in events)
    assert any(event.event_type == "CAPTURE_COMPLETED" for event in events)


@pytest.mark.asyncio
@pytest.mark.parametrize(("capture_status", "attempt_status", "reservation_status"), [
    ("COMPLETED", "SUCCEEDED", "CAPTURED"),
    ("PENDING", "UNKNOWN", "OUTCOME_UNKNOWN"),
    ("DECLINED", "FAILED", "CANCELLED"),
    ("FAILED", "FAILED", "CANCELLED"),
])
async def test_provider_capture_status_maps_to_existing_payment_states(capture_status, attempt_status, reservation_status):
    attempt_id, reservation_id, actor_id, _, _, paypal = await approved_payment()
    paypal.capture_status = capture_status
    result = await run_capture(attempt_id, actor_id, paypal)
    async with SessionLocal() as db:
        attempt = await db.get(PaymentAttemptRecord, attempt_id)
        reservation = await db.get(PaymentReservationRecord, reservation_id)
    assert result.state == attempt_status
    assert attempt.status == attempt_status
    assert reservation.status == reservation_status
    assert attempt.capture_id == paypal.capture_id


@pytest.mark.asyncio
async def test_unapproved_expired_revoked_or_mismatched_approval_cannot_claim_capture():
    attempt_id = await create_claimed_attempt()
    async with SessionLocal() as db:
        attempt = await db.get(PaymentAttemptRecord, attempt_id)
        reservation = await db.get(PaymentReservationRecord, attempt.reservation_id)
        actor_id = reservation.actor_id
    paypal = MockPayPal(f"MOCK-NO-APPROVAL-{uuid.uuid4().hex}")
    async with SessionLocal() as db:
        with pytest.raises(PaymentCaptureError):
            await capture_approved_payment(db, attempt_id=attempt_id, actor_id=actor_id,
                registry=make_registry(), paypal=paypal)
    assert paypal.capture_calls == 0

    # A verified approval is then invalidated separately for each authorization check.
    attempt_id, _, actor_id, _, _, paypal = await approved_payment(timedelta(seconds=0.5))
    await asyncio.sleep(0.55)
    async with SessionLocal() as db:
        with pytest.raises(PaymentCaptureError):
            await capture_approved_payment(db, attempt_id=attempt_id, actor_id=actor_id,
                registry=make_registry(), paypal=paypal)
    assert paypal.capture_calls == 0

    for change in ("revoked", "merchant", "amount", "currency"):
        attempt_id, _, actor_id, _, handoff, paypal = await approved_payment()
        async with SessionLocal() as db:
            attempt = await db.get(PaymentAttemptRecord, attempt_id)
            reservation = await db.get(PaymentReservationRecord, attempt.reservation_id)
            if change == "revoked":
                await db.execute(update(IntentContractRecord).where(
                    IntentContractRecord.id == reservation.contract_id,
                ).values(status="REVOKED", version=IntentContractRecord.version + 1))
            elif change == "merchant":
                await db.execute(update(PaymentCheckoutApprovalRecord).where(
                    PaymentCheckoutApprovalRecord.attempt_id == attempt_id,
                ).values(verified_merchant_id="OTHER-MERCHANT"))
            elif change == "amount":
                await db.execute(update(PaymentCheckoutApprovalRecord).where(
                    PaymentCheckoutApprovalRecord.attempt_id == attempt_id,
                ).values(verified_amount=Decimal("39.00")))
            elif change == "currency":
                await db.execute(update(PaymentCheckoutApprovalRecord).where(
                    PaymentCheckoutApprovalRecord.attempt_id == attempt_id,
                ).values(verified_currency="CAD"))
            await db.commit()
        async with SessionLocal() as db:
            with pytest.raises(PaymentCaptureError):
                await capture_approved_payment(db, attempt_id=attempt_id, actor_id=actor_id,
                    registry=make_registry(), paypal=paypal)
        assert paypal.capture_calls == 0


@pytest.mark.asyncio
async def test_concurrent_and_duplicate_capture_requests_call_provider_once():
    attempt_id, _, actor_id, _, _, paypal = await approved_payment()
    paypal.gate = asyncio.Event()
    first = asyncio.create_task(capture_approved_payment(SessionLocal(), attempt_id=attempt_id,
        actor_id=actor_id, registry=make_registry(), paypal=paypal))
    while paypal.capture_calls < 1:
        await asyncio.sleep(0)
    second = await run_capture(attempt_id, actor_id, paypal)
    assert second.action == "ALREADY_CLAIMED"
    assert second.state == "UNKNOWN"
    assert paypal.capture_calls == 1
    paypal.gate.set()
    result = await first
    assert result.state == "SUCCEEDED"
    third = await run_capture(attempt_id, actor_id, paypal)
    assert third.action == "ALREADY_CLAIMED"
    assert third.state == "SUCCEEDED"
    assert paypal.capture_calls == 1


@pytest.mark.asyncio
async def test_timeout_and_malformed_response_remain_unknown_and_retain_budget():
    for mode in ("timeout", "malformed", "wrong-order", "wrong-merchant", "wrong-amount", "wrong-currency"):
        attempt_id, reservation_id, actor_id, _, _, paypal = await approved_payment()
        if mode == "timeout":
            paypal.capture_error = PayPalCaptureOutcomeUnknownError("simulated timeout")
        else:
            paypal.capture_response = paypal._order(include_capture=True)
            unit = paypal.capture_response["purchase_units"][0]
            if mode == "malformed": paypal.capture_response["purchase_units"] = []
            elif mode == "wrong-order": paypal.capture_response["id"] = "OTHER-ORDER"
            elif mode == "wrong-merchant": unit["payee"]["merchant_id"] = "OTHER-MERCHANT"
            elif mode == "wrong-amount": unit["payments"]["captures"][0]["amount"]["value"] = "39.00"
            elif mode == "wrong-currency": unit["payments"]["captures"][0]["amount"]["currency_code"] = "CAD"
        result = await run_capture(attempt_id, actor_id, paypal)
        async with SessionLocal() as db:
            attempt = await db.get(PaymentAttemptRecord, attempt_id)
            reservation = await db.get(PaymentReservationRecord, reservation_id)
        assert result.state == "UNKNOWN"
        assert attempt.status == "UNKNOWN"
        assert reservation.status == "OUTCOME_UNKNOWN"
        assert attempt.capture_claimed_at is not None
        assert paypal.capture_calls == 1


@pytest.mark.asyncio
async def test_authentication_failure_before_capture_submission_is_definite_failure():
    attempt_id, reservation_id, actor_id, _, _, paypal = await approved_payment()
    paypal.capture_error = PayPalCaptureNotSubmittedError("authentication unavailable")
    result = await run_capture(attempt_id, actor_id, paypal)
    async with SessionLocal() as db:
        attempt = await db.get(PaymentAttemptRecord, attempt_id)
        reservation = await db.get(PaymentReservationRecord, reservation_id)
    assert result.state == "FAILED"
    assert attempt.capture_claimed_at is not None
    assert attempt.capture_id is None
    assert reservation.status == "CANCELLED"
    assert paypal.capture_calls == 1


@pytest.mark.asyncio
async def test_crash_after_durable_claim_cannot_trigger_second_provider_call():
    attempt_id, reservation_id, actor_id, _, _, paypal = await approved_payment()
    async with SessionLocal() as db:
        claim = await claim_payment_capture(db, attempt_id=attempt_id,
            actor_id=actor_id, registry=make_registry())
    assert claim.idempotency_key
    async with SessionLocal() as db:
        attempt = await db.get(PaymentAttemptRecord, attempt_id)
        reservation = await db.get(PaymentReservationRecord, reservation_id)
    assert attempt.status == "UNKNOWN"
    assert reservation.status == "OUTCOME_UNKNOWN"
    retry = await run_capture(attempt_id, actor_id, paypal)
    assert retry.action == "ALREADY_CLAIMED"
    assert paypal.capture_calls == 0


@pytest.mark.asyncio
async def test_unconsumed_return_state_is_not_valid_buyer_approval():
    attempt_id, _, actor_id, _, _, paypal = await approved_payment()
    async with SessionLocal() as db:
        await db.execute(update(PaymentCheckoutApprovalRecord).where(
            PaymentCheckoutApprovalRecord.attempt_id == attempt_id,
        ).values(consumed_at=None))
        await db.commit()
    with pytest.raises(PaymentCaptureError):
        await run_capture(attempt_id, actor_id, paypal)
    assert paypal.capture_calls == 0


@pytest.mark.asyncio
async def test_capture_id_unique_conflict_keeps_second_payment_unknown():
    first_id, _, first_actor, _, _, first_paypal = await approved_payment()
    first = await run_capture(first_id, first_actor, first_paypal)
    assert first.state == "SUCCEEDED"
    second_id, second_reservation_id, second_actor, _, _, second_paypal = await approved_payment()
    second_paypal.capture_id = first.capture_id
    result = await run_capture(second_id, second_actor, second_paypal)
    async with SessionLocal() as db:
        attempt = await db.get(PaymentAttemptRecord, second_id)
        reservation = await db.get(PaymentReservationRecord, second_reservation_id)
    assert result.state == "UNKNOWN"
    assert attempt.status == "UNKNOWN"
    assert attempt.capture_id is None
    assert reservation.status == "OUTCOME_UNKNOWN"


@pytest.mark.asyncio
async def test_contract_revocation_after_committed_claim_does_not_hide_capture():
    attempt_id, _, actor_id, _, _, paypal = await approved_payment()
    paypal.gate = asyncio.Event()
    capture = asyncio.create_task(run_capture(attempt_id, actor_id, paypal))
    while paypal.capture_calls < 1:
        await asyncio.sleep(0)
    async with SessionLocal() as db:
        attempt = await db.get(PaymentAttemptRecord, attempt_id)
        reservation = await db.get(PaymentReservationRecord, attempt.reservation_id)
        await db.execute(update(IntentContractRecord).where(
            IntentContractRecord.id == reservation.contract_id,
        ).values(status="REVOKED", version=IntentContractRecord.version + 1))
        await db.commit()
    paypal.gate.set()
    result = await capture
    assert result.state == "SUCCEEDED"


@pytest.mark.asyncio
async def test_wrong_owner_cannot_claim_or_capture():
    attempt_id, _, _, _, _, paypal = await approved_payment()
    with pytest.raises(PaymentCaptureError):
        await run_capture(attempt_id, uuid.uuid4(), paypal)
    assert paypal.capture_calls == 0
