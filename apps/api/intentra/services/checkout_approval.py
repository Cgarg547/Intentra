"""Durable, single-use buyer approval verification for PayPal checkout."""

import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from intentra.models.intent_contract import IntentContractRecord
from intentra.models.payment_attempt import PaymentAttemptRecord
from intentra.models.payment_attempt_event import PaymentAttemptEventRecord
from intentra.models.payment_checkout_approval import PaymentCheckoutApprovalRecord
from intentra.models.payment_reservation import PaymentReservationRecord
from intentra.services.merchant_registry import TrustedMerchantRegistry
from intentra.services.paypal_sandbox import PayPalSandboxClient, PayPalSandboxError


class CheckoutApprovalError(Exception):
    """Safe domain failure; route layer maps to generic HTTP errors."""


@dataclass(frozen=True)
class CheckoutHandoff:
    approval_id: uuid.UUID
    attempt_id: uuid.UUID
    provider_order_id: str
    return_state: str
    expires_at: datetime


@dataclass(frozen=True)
class CheckoutVerification:
    approval_id: uuid.UUID
    attempt_id: uuid.UUID
    state: str
    verified_at: datetime | None


def _event(db, attempt_id, actor_id, event_type, correlation_id, data=None):
    # The applied schema makes each event correlation unique. Preserve the
    # checkout-wide correlation in event data while assigning an event ID here.
    event_data = dict(data or {})
    event_data.setdefault("checkout_correlation_id", str(correlation_id))
    db.add(PaymentAttemptEventRecord(
        attempt_id=attempt_id,
        actor_id=actor_id,
        event_type=event_type,
        event_correlation_id=uuid.uuid4(),
        event_data=event_data,
    ))


async def initiate_checkout_approval(
    db: AsyncSession,
    *,
    attempt_id: uuid.UUID,
    actor_id: uuid.UUID,
    registry: TrustedMerchantRegistry,
    paypal: PayPalSandboxClient,
    lifetime: timedelta = timedelta(minutes=30),
) -> CheckoutHandoff:
    if lifetime <= timedelta(0) or lifetime > timedelta(hours=2):
        raise CheckoutApprovalError("Invalid checkout lifetime.")
    resume_approval_id = None
    previous_state_hash = None
    try:
        async with db.begin():
            attempt_ref = await db.get(PaymentAttemptRecord, attempt_id)
            if attempt_ref is None:
                raise CheckoutApprovalError("Checkout unavailable.")
            reservation_ref = await db.get(PaymentReservationRecord, attempt_ref.reservation_id)
            if reservation_ref is None or reservation_ref.actor_id != actor_id:
                raise CheckoutApprovalError("Checkout unavailable.")
            contract = await db.scalar(select(IntentContractRecord).where(
                IntentContractRecord.id == reservation_ref.contract_id,
                IntentContractRecord.owner_id == actor_id,
            ).with_for_update().execution_options(populate_existing=True))
            if contract is None:
                raise CheckoutApprovalError("Checkout unavailable.")
            reservation = await db.scalar(select(PaymentReservationRecord).where(
                PaymentReservationRecord.id == reservation_ref.id,
            ).with_for_update().execution_options(populate_existing=True))
            attempt = await db.scalar(select(PaymentAttemptRecord).where(
                PaymentAttemptRecord.id == attempt_id,
            ).with_for_update().execution_options(populate_existing=True))
            if reservation is None or attempt is None:
                raise CheckoutApprovalError("Checkout unavailable.")
            existing = await db.scalar(select(PaymentCheckoutApprovalRecord).where(
                PaymentCheckoutApprovalRecord.attempt_id == attempt.id,
            ).with_for_update())
            if existing is not None:
                if existing.state != "PENDING" or existing.expires_at <= datetime.now(timezone.utc):
                    raise CheckoutApprovalError("Checkout is no longer available.")
                if existing.consumed_at is not None:
                    raise CheckoutApprovalError("Checkout is no longer available.")
                # The raw one-time state exists only in the original browser
                # response/cookie. Rotate its hash when the owner resumes so
                # only the newly issued state can complete this approval.
                resume_approval_id = existing.id
                previous_state_hash = existing.return_state_hash
            if (contract.status != "APPROVED" or contract.version != reservation.contract_version
                or reservation.status != "EXECUTION_PENDING" or attempt.status != "PENDING"
                or not attempt.provider_order_id or reservation.amount <= 0
                or reservation.amount > contract.maximum_amount
                or reservation.merchant_id != contract.merchant_id
                or reservation.currency != contract.currency):
                raise CheckoutApprovalError("Checkout is not eligible.")
            merchant = registry.resolve(reservation.merchant_id)
            order_id = attempt.provider_order_id
            amount, currency = reservation.amount, reservation.currency
    except IntegrityError as exc:
        await db.rollback()
        raise CheckoutApprovalError("Checkout already initiated.") from exc

    # Provider request occurs without holding database locks.
    try:
        order = await paypal.get_order(
            order_id=order_id,
            expected_paypal_merchant_id=merchant.paypal_merchant_id,
            amount=amount,
            currency=currency,
        )
    except PayPalSandboxError as exc:
        raise CheckoutApprovalError("PayPal order verification unavailable.") from exc
    if order.get("status") not in {"CREATED", "PAYER_ACTION_REQUIRED"}:
        raise CheckoutApprovalError("PayPal order is not awaiting buyer approval.")

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    approval_id = uuid.uuid4()
    correlation_id = uuid.uuid4()
    async with db.begin():
        contract, reservation, attempt = await _lock_current(db, attempt_id, actor_id)
        if (contract.status != "APPROVED" or contract.version != reservation.contract_version
            or reservation.status != "EXECUTION_PENDING" or attempt.status != "PENDING"
            or attempt.provider_order_id != order_id or reservation.amount != amount
            or reservation.currency != currency or reservation.merchant_id != merchant.internal_merchant_id):
            raise CheckoutApprovalError("Checkout state changed during provider verification.")
        if await db.scalar(select(PaymentCheckoutApprovalRecord.id).where(
            PaymentCheckoutApprovalRecord.attempt_id == attempt_id,
        )):
            if resume_approval_id is None:
                raise CheckoutApprovalError("Checkout already initiated.")
        elif resume_approval_id is not None:
            raise CheckoutApprovalError("Checkout state changed during verification.")
        # Start the lifetime only after the authoritative locks and provider
        # verification are complete, immediately before the durable insert.
        now = datetime.now(timezone.utc)
        expires_at = now + lifetime
        if resume_approval_id is not None:
            approval = await db.scalar(select(PaymentCheckoutApprovalRecord).where(
                PaymentCheckoutApprovalRecord.id == resume_approval_id,
            ).with_for_update().execution_options(populate_existing=True))
            if (approval is None or approval.attempt_id != attempt_id
                or approval.provider_order_id != order_id or approval.state != "PENDING"
                or approval.consumed_at is not None or approval.expires_at <= now
                or approval.return_state_hash != previous_state_hash):
                raise CheckoutApprovalError("Checkout state changed during verification.")
            approval.return_state_hash = token_hash
            approval.expires_at = expires_at
            approval_id = approval.id
            correlation_id = approval.audit_correlation_id
            event_type = "CHECKOUT_HANDOFF_RESUMED"
        else:
            db.add(PaymentCheckoutApprovalRecord(
                id=approval_id, attempt_id=attempt_id, provider_order_id=order_id,
                state="PENDING", expires_at=expires_at, return_state_hash=token_hash,
                audit_correlation_id=correlation_id,
            ))
            event_type = "CHECKOUT_CREATED"
        _event(db, attempt_id, actor_id, event_type, correlation_id,
               {"approval_id": str(approval_id), "provider_order_id": order_id})
        await db.flush()
    return CheckoutHandoff(approval_id, attempt_id, order_id, raw_token, expires_at)


async def _lock_current(db, attempt_id, actor_id):
    ref = await db.get(PaymentAttemptRecord, attempt_id)
    if ref is None:
        raise CheckoutApprovalError("Checkout unavailable.")
    rref = await db.get(PaymentReservationRecord, ref.reservation_id)
    if rref is None or rref.actor_id != actor_id:
        raise CheckoutApprovalError("Checkout unavailable.")
    contract = await db.scalar(select(IntentContractRecord).where(
        IntentContractRecord.id == rref.contract_id,
        IntentContractRecord.owner_id == actor_id,
    ).with_for_update().execution_options(populate_existing=True))
    reservation = await db.scalar(select(PaymentReservationRecord).where(
        PaymentReservationRecord.id == rref.id,
    ).with_for_update().execution_options(populate_existing=True))
    attempt = await db.scalar(select(PaymentAttemptRecord).where(
        PaymentAttemptRecord.id == attempt_id,
    ).with_for_update().execution_options(populate_existing=True))
    if contract is None or reservation is None or attempt is None:
        raise CheckoutApprovalError("Checkout unavailable.")
    return contract, reservation, attempt


async def verify_checkout_return(
    db: AsyncSession,
    *,
    attempt_id: uuid.UUID,
    actor_id: uuid.UUID,
    return_state: str,
    registry: TrustedMerchantRegistry,
    paypal: PayPalSandboxClient,
) -> CheckoutVerification:
    if not return_state or len(return_state) > 128:
        raise CheckoutApprovalError("Checkout return is invalid.")
    token_hash = hashlib.sha256(return_state.encode()).hexdigest()
    async with db.begin():
        contract, reservation, attempt = await _lock_current(db, attempt_id, actor_id)
        approval = await db.scalar(select(PaymentCheckoutApprovalRecord).where(
            PaymentCheckoutApprovalRecord.attempt_id == attempt_id,
            PaymentCheckoutApprovalRecord.return_state_hash == token_hash,
        ).with_for_update().execution_options(populate_existing=True))
        if approval is not None and not hmac.compare_digest(approval.return_state_hash, token_hash):
            approval = None
        if approval is None:
            raise CheckoutApprovalError("Checkout return is invalid.")
        if approval.state != "PENDING" or approval.consumed_at is not None:
            raise CheckoutApprovalError("Checkout return was already used.")
        now = datetime.now(timezone.utc)
        if approval.expires_at <= now:
            approval.state = "EXPIRED"
            approval.consumed_at = now
            _event(db, attempt_id, actor_id, "CHECKOUT_EXPIRED", approval.audit_correlation_id)
            await db.flush()
            return CheckoutVerification(approval.id, attempt_id, "EXPIRED", None)
        if (contract.status != "APPROVED" or contract.version != reservation.contract_version
            or reservation.status != "EXECUTION_PENDING" or attempt.status != "PENDING"
            or attempt.provider_order_id != approval.provider_order_id):
            raise CheckoutApprovalError("Checkout is no longer authorized.")
        snapshot = (approval.id, approval.provider_order_id, reservation.merchant_id,
                    reservation.amount, reservation.currency, reservation.contract_version)

    merchant = registry.resolve(snapshot[2])
    try:
        order = await paypal.get_order(order_id=snapshot[1],
            expected_paypal_merchant_id=merchant.paypal_merchant_id,
            amount=snapshot[3], currency=snapshot[4])
    except PayPalSandboxError:
        raise CheckoutApprovalError("PayPal verification is temporarily unavailable.")

    provider_status = order.get("status")
    # get_order validates ID, one purchase unit, payee and amount. Only APPROVED is accepted.
    if provider_status != "APPROVED":
        raise CheckoutApprovalError("PayPal order is not approved.")
    units = order.get("purchase_units")
    if not isinstance(units, list) or len(units) != 1 or not isinstance(units[0], dict):
        raise CheckoutApprovalError("PayPal order is invalid.")
    now = datetime.now(timezone.utc)
    async with db.begin():
        contract, reservation, attempt = await _lock_current(db, attempt_id, actor_id)
        approval = await db.scalar(select(PaymentCheckoutApprovalRecord).where(
            PaymentCheckoutApprovalRecord.id == snapshot[0],
        ).with_for_update().execution_options(populate_existing=True))
        if (approval is None or approval.state != "PENDING" or approval.consumed_at is not None
            or approval.expires_at <= now or approval.provider_order_id != snapshot[1]
            or attempt.provider_order_id != snapshot[1]
            or reservation.amount != snapshot[3] or reservation.currency != snapshot[4]
            or reservation.merchant_id != snapshot[2]
            or reservation.contract_version != snapshot[5]
            or contract.status != "APPROVED" or contract.version != snapshot[5]):
            raise CheckoutApprovalError("Checkout state changed during verification.")
        unit = units[0]
        approval.state = "APPROVED"
        approval.verified_provider_status = "APPROVED"
        approval.verified_merchant_id = merchant.paypal_merchant_id
        approval.verified_amount = snapshot[3]
        approval.verified_currency = snapshot[4]
        approval.verified_at = now
        approval.consumed_at = now
        _event(db, attempt_id, actor_id, "CHECKOUT_APPROVED", approval.audit_correlation_id,
               {"approval_id": str(approval.id), "provider_order_id": snapshot[1],
                "provider_status": "APPROVED", "merchant_id": merchant.paypal_merchant_id,
                "amount": str(snapshot[3]), "currency": snapshot[4]})
        await db.flush()
        return CheckoutVerification(approval.id, attempt_id, approval.state, now)


async def cancel_checkout(
    db: AsyncSession, *, attempt_id: uuid.UUID, actor_id: uuid.UUID,
    return_state: str,
) -> CheckoutVerification:
    """Consume the owner's pending checkout after a PayPal cancel return."""
    if not return_state or len(return_state) > 128:
        raise CheckoutApprovalError("Checkout return is invalid.")
    token_hash = hashlib.sha256(return_state.encode()).hexdigest()
    async with db.begin():
        _, reservation, attempt = await _lock_current(db, attempt_id, actor_id)
        approval = await db.scalar(select(PaymentCheckoutApprovalRecord).where(
            PaymentCheckoutApprovalRecord.attempt_id == attempt_id,
            PaymentCheckoutApprovalRecord.return_state_hash == token_hash,
        ).with_for_update().execution_options(populate_existing=True))
        if approval is None or not hmac.compare_digest(approval.return_state_hash, token_hash):
            raise CheckoutApprovalError("Checkout return is invalid.")
        if approval.state != "PENDING" or approval.consumed_at is not None:
            raise CheckoutApprovalError("Checkout return was already used.")
        now = datetime.now(timezone.utc)
        if approval.expires_at <= now:
            approval.state = "EXPIRED"
            event_type = "CHECKOUT_EXPIRED"
        else:
            approval.state = "CANCELLED"
            event_type = "CHECKOUT_CANCELLED"
        approval.consumed_at = now
        _event(db, attempt_id, actor_id, event_type, approval.audit_correlation_id,
               {"approval_id": str(approval.id), "provider_order_id": approval.provider_order_id})
        await db.flush()
        return CheckoutVerification(approval.id, attempt_id, approval.state, None)
