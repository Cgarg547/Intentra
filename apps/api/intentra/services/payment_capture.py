"""Durable single-shot capture execution for buyer-approved PayPal orders."""

import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from intentra.models.intent_contract import IntentContractRecord
from intentra.models.payment_attempt import PaymentAttemptRecord
from intentra.models.payment_attempt_event import PaymentAttemptEventRecord
from intentra.models.payment_checkout_approval import PaymentCheckoutApprovalRecord
from intentra.models.payment_reservation import PaymentReservationRecord
from intentra.services.merchant_registry import MerchantRegistryError, TrustedMerchantRegistry
from intentra.services.paypal_sandbox import (
    PayPalCaptureNotSubmittedError,
    PayPalSandboxClient,
    PayPalSandboxError,
    validate_paypal_capture,
)


class PaymentCaptureError(Exception):
    """Safe capture workflow failure."""


@dataclass(frozen=True)
class CaptureResult:
    attempt_id: uuid.UUID
    state: str
    capture_id: str | None
    action: str


@dataclass(frozen=True)
class CaptureClaim:
    attempt_id: uuid.UUID
    actor_id: uuid.UUID
    order_id: str
    merchant_id: str
    expected_paypal_merchant_id: str
    amount: Decimal
    currency: str
    idempotency_key: str
    approval_id: uuid.UUID
    operation_id: uuid.UUID


def _add_attempt_event(db, *, attempt_id, actor_id, event_type, operation_id, data):
    # event_correlation_id is unique per row in the applied schema. Keep the
    # capture operation correlation in the immutable JSON payload.
    payload = dict(data)
    payload["operation_id"] = str(operation_id)
    db.add(PaymentAttemptEventRecord(
        attempt_id=attempt_id,
        actor_id=actor_id,
        event_type=event_type,
        event_correlation_id=uuid.uuid4(),
        event_data=payload,
    ))


async def _locked_records(db, *, attempt_id: uuid.UUID, actor_id: uuid.UUID):
    attempt_ref = await db.get(PaymentAttemptRecord, attempt_id)
    if attempt_ref is None:
        raise PaymentCaptureError("Payment is unavailable.")
    reservation_ref = await db.get(PaymentReservationRecord, attempt_ref.reservation_id)
    if reservation_ref is None or reservation_ref.actor_id != actor_id:
        raise PaymentCaptureError("Payment is unavailable.")
    contract = await db.scalar(select(IntentContractRecord).where(
        IntentContractRecord.id == reservation_ref.contract_id,
        IntentContractRecord.owner_id == actor_id,
    ).with_for_update().execution_options(populate_existing=True))
    if contract is None:
        raise PaymentCaptureError("Payment is unavailable.")
    reservation = await db.scalar(select(PaymentReservationRecord).where(
        PaymentReservationRecord.id == reservation_ref.id,
    ).with_for_update().execution_options(populate_existing=True))
    attempt = await db.scalar(select(PaymentAttemptRecord).where(
        PaymentAttemptRecord.id == attempt_id,
    ).with_for_update().execution_options(populate_existing=True))
    if reservation is None or attempt is None:
        raise PaymentCaptureError("Payment is unavailable.")
    if (attempt.reservation_id != reservation.id
        or reservation.contract_id != contract.id
        or reservation.actor_id != actor_id):
        raise PaymentCaptureError("Payment is unavailable.")
    approval = await db.scalar(select(PaymentCheckoutApprovalRecord).where(
        PaymentCheckoutApprovalRecord.attempt_id == attempt_id,
    ).with_for_update().execution_options(populate_existing=True))
    if approval is None:
        raise PaymentCaptureError("Buyer approval is required.")
    return contract, reservation, attempt, approval


async def claim_payment_capture(
    db: AsyncSession,
    *,
    attempt_id: uuid.UUID,
    actor_id: uuid.UUID,
    registry: TrustedMerchantRegistry,
) -> CaptureClaim | CaptureResult:
    """Commit a one-time claim before any PayPal capture network request."""
    operation_id = uuid.uuid4()
    async with db.begin():
        contract, reservation, attempt, approval = await _locked_records(
            db, attempt_id=attempt_id, actor_id=actor_id,
        )

        if attempt.capture_claimed_at is not None or attempt.capture_idempotency_key is not None:
            return CaptureResult(
                attempt_id=attempt.id,
                state=attempt.status,
                capture_id=attempt.capture_id,
                action="ALREADY_CLAIMED",
            )
        if (contract.status != "APPROVED"
            or contract.version != reservation.contract_version
            or reservation.status != "EXECUTION_PENDING"
            or attempt.status != "PENDING"
            or approval.state != "APPROVED"
            or approval.consumed_at is None
            or approval.expires_at <= datetime.now(timezone.utc)
            or approval.provider_order_id != attempt.provider_order_id
            or not attempt.provider_order_id
            or approval.verified_provider_status != "APPROVED"
            or approval.verified_amount != reservation.amount
            or approval.verified_currency != reservation.currency
            or approval.verified_merchant_id is None
            or reservation.merchant_id != contract.merchant_id
            or reservation.currency != contract.currency
            or reservation.amount <= 0
            or reservation.amount > contract.maximum_amount):
            raise PaymentCaptureError("Payment is not eligible for capture.")

        try:
            trusted_merchant = registry.resolve(reservation.merchant_id)
        except MerchantRegistryError as exc:
            raise PaymentCaptureError("Authorized merchant is unavailable.") from exc
        if approval.verified_merchant_id != trusted_merchant.paypal_merchant_id:
            raise PaymentCaptureError("Verified merchant does not match the authorized merchant.")

        # PayPal keys are independent of create-order keys and persisted once.
        capture_key = secrets.token_hex(32)
        attempt.capture_idempotency_key = capture_key
        attempt.capture_claimed_at = datetime.now(timezone.utc)
        # A committed claim means the request may be sent. Treat it as unknown
        # immediately so a crash cannot make the budget available again.
        attempt.status = "UNKNOWN"
        reservation.status = "OUTCOME_UNKNOWN"
        reservation.reason = "PayPal capture claimed; reconciliation is required until confirmed."
        _add_attempt_event(db, attempt_id=attempt.id, actor_id=actor_id,
            event_type="CAPTURE_CLAIMED", operation_id=operation_id,
            data={"provider_order_id": attempt.provider_order_id,
                  "approval_id": str(approval.id)})
        await db.flush()
        return CaptureClaim(
            attempt_id=attempt.id,
            actor_id=actor_id,
            order_id=attempt.provider_order_id,
            merchant_id=reservation.merchant_id,
            expected_paypal_merchant_id=trusted_merchant.paypal_merchant_id,
            amount=reservation.amount,
            currency=reservation.currency,
            idempotency_key=capture_key,
            approval_id=approval.id,
            operation_id=operation_id,
        )


async def _persist_capture_result(
    db: AsyncSession,
    *,
    claim: CaptureClaim,
    actor_id: uuid.UUID | None,
    capture_id: str | None,
    provider_status: str,
    event_suffix: str,
    operation_id: uuid.UUID | None = None,
    expected_snapshot: tuple | None = None,
    reconciliation_evidence: dict | None = None,
):
    op_id = operation_id or claim.operation_id
    async with db.begin():
        contract, reservation, attempt, approval = await _locked_records(
            db, attempt_id=claim.attempt_id, actor_id=claim.actor_id,
        )
        if (attempt.capture_idempotency_key != claim.idempotency_key
            or attempt.capture_claimed_at is None
            or attempt.provider_order_id != claim.order_id
            or approval.id != claim.approval_id
            or approval.provider_order_id != claim.order_id
            or approval.state != "APPROVED"
            or approval.consumed_at is None
            or approval.verified_provider_status != "APPROVED"
            or approval.verified_merchant_id != claim.expected_paypal_merchant_id
            or approval.verified_amount != claim.amount
            or approval.verified_currency != claim.currency
            or reservation.merchant_id != claim.merchant_id
            or reservation.amount != claim.amount
            or reservation.currency != claim.currency):
            raise PaymentCaptureError("Capture state changed; reconciliation is required.")
        current_snapshot = _capture_snapshot(attempt, reservation)
        if expected_snapshot is not None and current_snapshot != expected_snapshot:
            raise PaymentCaptureError("Payment state changed during reconciliation.")
        if attempt.status != "UNKNOWN" or reservation.status != "OUTCOME_UNKNOWN":
            raise PaymentCaptureError("Capture outcome is already terminal or inconsistent.")

        outcome = {
            "COMPLETED": ("SUCCEEDED", "CAPTURED", "CAPTURE_COMPLETED"),
            "DECLINED": ("FAILED", "CANCELLED", "CAPTURE_DECLINED"),
            "FAILED": ("FAILED", "CANCELLED", "CAPTURE_FAILED"),
            "PENDING": ("UNKNOWN", "OUTCOME_UNKNOWN", "CAPTURE_PENDING"),
            "UNKNOWN": ("UNKNOWN", "OUTCOME_UNKNOWN", "CAPTURE_OUTCOME_UNKNOWN"),
            "NOT_SUBMITTED": ("FAILED", "CANCELLED", "CAPTURE_NOT_SUBMITTED"),
        }.get(provider_status)
        if outcome is None:
            raise PaymentCaptureError("Unsupported provider capture state.")
        attempt.status, reservation.status, event_type = outcome
        if capture_id is not None:
            if attempt.capture_id is not None and attempt.capture_id != capture_id:
                raise PaymentCaptureError("Conflicting PayPal capture identity.")
            attempt.capture_id = capture_id
        reservation.reason = {
            "SUCCEEDED": "Provider-confirmed PayPal capture.",
            "FAILED": "Provider confirmed no payment was captured.",
            "UNKNOWN": "PayPal capture outcome requires reconciliation.",
        }[attempt.status]
        _add_attempt_event(db, attempt_id=attempt.id, actor_id=actor_id,
            event_type=event_type, operation_id=op_id,
            data={"provider_order_id": claim.order_id,
                  "capture_id": capture_id,
                  "provider_status": provider_status})

        if reconciliation_evidence is not None:
            from intentra.services.payment_reconciliation_evidence import (
                record_reconciliation_evidence,
            )
            await record_reconciliation_evidence(
                db,
                operation_id=op_id,
                attempt_id=claim.attempt_id,
                event_type=event_suffix,
                provider_order_id=claim.order_id,
                provider_status=provider_status,
                evidence_data=reconciliation_evidence,
            )
        await db.flush()
        return CaptureResult(attempt.id, attempt.status, attempt.capture_id, event_type)


def _capture_snapshot(attempt, reservation):
    return (
        attempt.id, attempt.reservation_id, attempt.status, attempt.provider_order_id,
        attempt.capture_idempotency_key, attempt.capture_claimed_at,
        attempt.capture_id, reservation.contract_id, reservation.contract_version,
        reservation.status, reservation.merchant_id, reservation.amount,
        reservation.currency,
    )


async def capture_approved_payment(
    db: AsyncSession,
    *,
    attempt_id: uuid.UUID,
    actor_id: uuid.UUID,
    registry: TrustedMerchantRegistry,
    paypal: PayPalSandboxClient,
) -> CaptureResult:
    claim = await claim_payment_capture(
        db, attempt_id=attempt_id, actor_id=actor_id, registry=registry,
    )
    if isinstance(claim, CaptureResult):
        return claim

    try:
        response = await paypal.capture_order(
            order_id=claim.order_id,
            expected_paypal_merchant_id=claim.expected_paypal_merchant_id,
            amount=claim.amount,
            currency=claim.currency,
            provider_idempotency_key=claim.idempotency_key,
        )
    except PayPalCaptureNotSubmittedError:
        return await _persist_capture_result(db, claim=claim, actor_id=actor_id,
            capture_id=None, provider_status="NOT_SUBMITTED", event_suffix="",
            operation_id=uuid.uuid4())
    except PayPalSandboxError:
        # Do not release the reservation or retry. The provider may have acted.
        async with db.begin():
            _add_attempt_event(db, attempt_id=attempt_id, actor_id=actor_id,
                event_type="CAPTURE_OUTCOME_UNKNOWN", operation_id=uuid.uuid4(),
                data={"provider_order_id": claim.order_id,
                      "reason_code": "PROVIDER_OUTCOME_UNCERTAIN"})
        return CaptureResult(attempt_id, "UNKNOWN", None, "RECONCILIATION_REQUIRED")

    try:
        status = validate_paypal_capture(
            response,
            order_id=claim.order_id,
            expected_paypal_merchant_id=claim.expected_paypal_merchant_id,
            amount=claim.amount,
            currency=claim.currency,
        )
        unit = response["purchase_units"][0]
        capture_id = unit["payments"]["captures"][0]["id"]
    except (PayPalSandboxError, KeyError, IndexError, TypeError):
        async with db.begin():
            _add_attempt_event(db, attempt_id=attempt_id, actor_id=actor_id,
                event_type="CAPTURE_OUTCOME_UNKNOWN", operation_id=uuid.uuid4(),
                data={"provider_order_id": claim.order_id,
                      "reason_code": "INVALID_PROVIDER_CAPTURE_RESPONSE"})
        return CaptureResult(attempt_id, "UNKNOWN", None, "RECONCILIATION_REQUIRED")

    try:
        return await _persist_capture_result(
            db, claim=claim, actor_id=actor_id, capture_id=capture_id,
            provider_status=status, event_suffix="", operation_id=claim.operation_id,
        )
    except IntegrityError:
        # A conflicting unique capture ID is not proof of failure. The durable
        # claim remains UNKNOWN and reconciliation/manual review is required.
        await db.rollback()
        return CaptureResult(attempt_id, "UNKNOWN", None, "RECONCILIATION_REQUIRED")


async def reconcile_capture_evidence(
    db: AsyncSession,
    *,
    claim: CaptureClaim,
    expected_snapshot: tuple,
    capture_id: str,
    provider_status: str,
    verified_merchant_id: str,
    verified_amount: str,
    verified_currency: str,
) -> CaptureResult:
    event_type = "ORDER_VERIFIED" if provider_status in {"COMPLETED", "DECLINED"} else "HOLD_FOR_REVIEW"
    evidence = {
        "reason_code": f"CAPTURE_{provider_status}",
        "capture_id": capture_id,
        "verified_merchant_id": verified_merchant_id,
        "verified_amount": verified_amount,
        "verified_currency": verified_currency,
    }
    return await _persist_capture_result(
        db, claim=claim, actor_id=None, capture_id=capture_id,
        provider_status=provider_status, event_suffix=event_type,
        operation_id=uuid.uuid4(), expected_snapshot=expected_snapshot,
        reconciliation_evidence=evidence,
    )


async def record_unresolved_capture_observation(
    db: AsyncSession,
    *,
    claim: CaptureClaim,
    expected_snapshot: tuple,
    reason_code: str,
    event_type: str,
    provider_status: str | None = None,
):
    """Append provider observation while retaining UNKNOWN and its budget."""
    from intentra.services.payment_reconciliation_evidence import (
        record_reconciliation_evidence,
    )
    operation_id = uuid.uuid4()
    async with db.begin():
        _, reservation, attempt, approval = await _locked_records(
            db, attempt_id=claim.attempt_id, actor_id=claim.actor_id,
        )
        if (_capture_snapshot(attempt, reservation) != expected_snapshot
            or attempt.capture_idempotency_key != claim.idempotency_key
            or approval.id != claim.approval_id
            or attempt.status != "UNKNOWN"
            or reservation.status != "OUTCOME_UNKNOWN"):
            raise PaymentCaptureError("Payment state changed during reconciliation.")
        _add_attempt_event(db, attempt_id=attempt.id, actor_id=None,
            event_type="CAPTURE_RECONCILIATION_UNRESOLVED",
            operation_id=operation_id,
            data={"provider_order_id": claim.order_id,
                  "reason_code": reason_code,
                  "provider_status": provider_status})
        await record_reconciliation_evidence(
            db, operation_id=operation_id, attempt_id=attempt.id,
            event_type=event_type, provider_order_id=claim.order_id,
            provider_status=provider_status,
            evidence_data={"reason_code": reason_code},
        )
    return CaptureResult(attempt.id, "UNKNOWN", attempt.capture_id, "RECONCILIATION_REQUIRED")
