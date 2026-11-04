import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from intentra.models.intent_contract import IntentContractRecord
from intentra.models.payment_attempt import PaymentAttemptRecord
from intentra.models.payment_checkout_approval import PaymentCheckoutApprovalRecord
from intentra.models.payment_reservation import PaymentReservationRecord
from intentra.services.payment_capture import (
    CaptureClaim,
    PaymentCaptureError,
    reconcile_capture_evidence,
    record_unresolved_capture_observation,
)
from intentra.services.merchant_registry import MerchantRegistryError, TrustedMerchantRegistry
from intentra.services.payment_reconciliation import (
    PaymentReconciliationError,
    plan_order_reconciliation,
)
from intentra.services.paypal_sandbox import (
    PayPalSandboxClient,
    PayPalSandboxError,
    validate_paypal_capture,
)


@dataclass(frozen=True)
class ReconciliationResult:
    attempt_id: uuid.UUID
    action: str
    provider_order_id: str | None
    provider_status: str | None
    capture_id: str | None = None


async def reconcile_payment_attempt(
    db: AsyncSession,
    *,
    attempt_id: uuid.UUID,
    registry: TrustedMerchantRegistry,
    paypal: PayPalSandboxClient,
    actor_id: uuid.UUID | None = None,
) -> ReconciliationResult:
    """
    Reconcile an existing payment attempt without initiating a new capture.

    The caller must provide a dedicated session with no active
    transaction. This function manages its own read transactions.

    Never creates or captures payments. Captured-operation evidence may move
    UNKNOWN to a verified terminal state while preserving the reservation.
    """
    if db.in_transaction():
        raise PaymentReconciliationError(
            "Reconciliation requires a session without an active transaction."
        )

    async with db.begin():
        attempt = await db.scalar(
            select(PaymentAttemptRecord).where(
                PaymentAttemptRecord.id == attempt_id
            )
        )

        if attempt is None:
            raise PaymentReconciliationError(
                "Payment attempt not found."
            )

        reservation = await db.scalar(
            select(PaymentReservationRecord).where(
                PaymentReservationRecord.id == attempt.reservation_id
            )
        )

        if reservation is None:
            raise PaymentReconciliationError(
                "Payment reservation not found."
            )

        if actor_id is not None and reservation.actor_id != actor_id:
            raise PaymentReconciliationError("Payment attempt not found.")
        if actor_id is not None:
            contract = await db.get(IntentContractRecord, reservation.contract_id)
            if contract is None or contract.owner_id != actor_id:
                raise PaymentReconciliationError("Payment attempt not found.")

        approval = None
        if attempt.capture_claimed_at is not None:
            approval = await db.scalar(select(PaymentCheckoutApprovalRecord).where(
                PaymentCheckoutApprovalRecord.attempt_id == attempt_id,
            ))
            if approval is None or approval.state != "APPROVED":
                raise PaymentReconciliationError("Capture approval evidence is unavailable.")

        capture_snapshot = (
            attempt.id, attempt.reservation_id, attempt.status,
            attempt.provider_order_id, attempt.capture_idempotency_key,
            attempt.capture_claimed_at, attempt.capture_id, reservation.contract_id,
            reservation.contract_version, reservation.status,
            reservation.merchant_id, reservation.amount, reservation.currency,
        )
        capture_claim = None
        if attempt.capture_claimed_at is not None:
            terminal_pair = {
                ("SUCCEEDED", "CAPTURED"),
                ("FAILED", "CANCELLED"),
            }
            if (attempt.status, reservation.status) in terminal_pair:
                return ReconciliationResult(
                    attempt_id=attempt_id, action="ALREADY_FINAL",
                    provider_order_id=attempt.provider_order_id,
                    provider_status=attempt.status, capture_id=attempt.capture_id,
                )
            try:
                merchant = registry.resolve(reservation.merchant_id)
            except MerchantRegistryError as exc:
                raise PaymentReconciliationError("Authorized merchant is unavailable.") from exc
            capture_claim = CaptureClaim(
                attempt_id=attempt.id,
                actor_id=reservation.actor_id,
                order_id=attempt.provider_order_id,
                merchant_id=reservation.merchant_id,
                expected_paypal_merchant_id=merchant.paypal_merchant_id,
                amount=reservation.amount,
                currency=reservation.currency,
                idempotency_key=attempt.capture_idempotency_key,
                approval_id=approval.id,
                operation_id=uuid.uuid4(),
            )

        snapshot = (
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

        decision = plan_order_reconciliation(
            attempt_status=attempt.status,
            reservation_status=reservation.status,
            provider_order_id=attempt.provider_order_id,
        )

    if decision.action == "HOLD_FOR_REVIEW":
        if capture_claim is not None:
            result = await record_unresolved_capture_observation(
                db, claim=capture_claim, expected_snapshot=capture_snapshot,
                reason_code="PROVIDER_ORDER_ID_MISSING", event_type="HOLD_FOR_REVIEW",
            )
            return ReconciliationResult(attempt_id, result.action, None, None)
        return ReconciliationResult(
            attempt_id=attempt_id,
            action="HOLD_FOR_REVIEW",
            provider_order_id=None,
            provider_status=None,
        )

    try:
        merchant = registry.resolve(snapshot[7])
    except MerchantRegistryError as exc:
        raise PaymentReconciliationError("Authorized merchant is unavailable.") from exc

    # No database transaction is held during external HTTP.
    try:
        order = await paypal.get_order(
            order_id=decision.provider_order_id,
            expected_paypal_merchant_id=merchant.paypal_merchant_id,
            amount=snapshot[8],
            currency=snapshot[9],
        )
    except PayPalSandboxError:
        if capture_claim is None:
            raise
        result = await record_unresolved_capture_observation(
            db, claim=capture_claim, expected_snapshot=capture_snapshot,
            reason_code="PROVIDER_LOOKUP_UNCERTAIN", event_type="LOOKUP_FAILED",
        )
        return ReconciliationResult(attempt_id, result.action, decision.provider_order_id, None)

    if capture_claim is not None:
        capture_id, capture_status = None, None
        try:
            units = order.get("purchase_units")
            if not isinstance(units, list) or len(units) != 1 or not isinstance(units[0], dict):
                raise PayPalSandboxError("Invalid purchase unit in reconciliation response.")
            payments = units[0].get("payments")
            captures = payments.get("captures") if isinstance(payments, dict) else None
            if captures is None or captures == []:
                result = await record_unresolved_capture_observation(
                    db, claim=capture_claim, expected_snapshot=capture_snapshot,
                    reason_code="CAPTURE_NOT_PRESENT_OR_NOT_YET_VISIBLE",
                    event_type="HOLD_FOR_REVIEW", provider_status=order.get("status"),
                )
                return ReconciliationResult(attempt_id, result.action, order["id"], order.get("status"))
            capture_status = validate_paypal_capture(
                order, order_id=capture_claim.order_id,
                expected_paypal_merchant_id=capture_claim.expected_paypal_merchant_id,
                amount=capture_claim.amount, currency=capture_claim.currency,
            )
            capture_id = captures[0]["id"]
            if attempt.capture_id is not None and attempt.capture_id != capture_id:
                raise PayPalSandboxError("Conflicting PayPal capture identity.")
        except (PayPalSandboxError, KeyError, IndexError, TypeError):
            result = await record_unresolved_capture_observation(
                db, claim=capture_claim, expected_snapshot=capture_snapshot,
                reason_code="CAPTURE_EVIDENCE_INVALID", event_type="VERIFICATION_REJECTED",
                provider_status=order.get("status"),
            )
            return ReconciliationResult(attempt_id, result.action, order.get("id"), order.get("status"))
        try:
            result = await reconcile_capture_evidence(
                db, claim=capture_claim, expected_snapshot=capture_snapshot,
                capture_id=capture_id, provider_status=capture_status,
                verified_merchant_id=capture_claim.expected_paypal_merchant_id,
                verified_amount=f"{capture_claim.amount:.2f}",
                verified_currency=capture_claim.currency,
            )
        except PaymentCaptureError as exc:
            raise PaymentReconciliationError(str(exc)) from exc
        return ReconciliationResult(
            attempt_id, result.action, order["id"], capture_status, capture_id,
        )

    # Force a fresh ORM read after the external lookup.
    db.expire_all()

    async with db.begin():
        current_attempt = await db.scalar(
            select(PaymentAttemptRecord).where(
                PaymentAttemptRecord.id == attempt_id
            )
        )

        if current_attempt is None:
            raise PaymentReconciliationError(
                "Payment state changed during provider lookup."
            )

        current_reservation = await db.scalar(
            select(PaymentReservationRecord).where(
                PaymentReservationRecord.id
                == current_attempt.reservation_id
            )
        )

        if current_reservation is None:
            raise PaymentReconciliationError(
                "Payment state changed during provider lookup."
            )

        current_snapshot = (
            current_attempt.id,
            current_attempt.reservation_id,
            current_attempt.status,
            current_attempt.provider_order_id,
            current_reservation.contract_id,
            current_reservation.contract_version,
            current_reservation.status,
            current_reservation.merchant_id,
            current_reservation.amount,
            current_reservation.currency,
        )

        if current_snapshot != snapshot:
            raise PaymentReconciliationError(
                "Payment state changed during provider lookup."
            )

    return ReconciliationResult(
        attempt_id=attempt_id,
        action="ORDER_VERIFIED",
        provider_order_id=order["id"],
        provider_status=order.get("status"),
    )
