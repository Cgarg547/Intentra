"""Operator-only recovery for a PayPal order accepted before local binding."""

import uuid
from dataclasses import dataclass
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
from intentra.services.paypal_sandbox import PayPalSandboxClient, PayPalSandboxError


class PaymentOrderRecoveryError(Exception):
    """Safe failure for a narrowly scoped operator recovery operation."""


@dataclass(frozen=True)
class PaymentOrderRecoveryResult:
    attempt_id: uuid.UUID
    provider_order_id: str
    changed: bool


def _has_capture(order: dict) -> bool:
    """Reject any capture evidence, including malformed nested structures."""
    units = order.get("purchase_units")
    if not isinstance(units, list) or len(units) != 1 or not isinstance(units[0], dict):
        return True
    payments = units[0].get("payments")
    if payments is None:
        return False
    if not isinstance(payments, dict):
        return True
    captures = payments.get("captures")
    if captures is None:
        return False
    return not isinstance(captures, list) or bool(captures)


async def recover_existing_paypal_order(
    db: AsyncSession,
    *,
    attempt_id: uuid.UUID,
    expected_reservation_id: uuid.UUID,
    expected_contract_id: uuid.UUID,
    expected_contract_version: int,
    provider_order_id: str,
    dashboard_correlation_attempt_id: uuid.UUID,
    expected_internal_merchant_id: str,
    expected_amount: Decimal,
    expected_currency: str,
    registry: TrustedMerchantRegistry,
    paypal: PayPalSandboxClient,
) -> PaymentOrderRecoveryResult:
    """GET, validate, then atomically bind one operator-correlated order.

    This function deliberately has no HTTP route. It is intended for an
    explicitly invoked local operator procedure, never a browser request.
    The dashboard correlation is required because a PayPal order GET does
    not expose the original return/cancel URL context.
    """
    if (
        dashboard_correlation_attempt_id != attempt_id
        or not isinstance(provider_order_id, str)
        or not provider_order_id
        or provider_order_id != provider_order_id.strip()
        or len(provider_order_id) > 128
        or not expected_amount.is_finite()
        or expected_amount <= 0
        or not isinstance(expected_currency, str)
        or len(expected_currency) != 3
    ):
        raise PaymentOrderRecoveryError("Recovery evidence is invalid.")

    # Read a snapshot only. The provider request must not run inside a DB
    # transaction or while holding locks.
    attempt_ref = await db.get(PaymentAttemptRecord, attempt_id)
    if attempt_ref is None:
        raise PaymentOrderRecoveryError("Recovery target is unavailable.")
    reservation_ref = await db.get(PaymentReservationRecord, attempt_ref.reservation_id)
    if reservation_ref is None:
        raise PaymentOrderRecoveryError("Recovery target is unavailable.")
    if (
        reservation_ref.id != expected_reservation_id
        or reservation_ref.contract_id != expected_contract_id
        or reservation_ref.contract_version != expected_contract_version
        or reservation_ref.merchant_id != expected_internal_merchant_id
        or reservation_ref.amount != expected_amount
        or reservation_ref.currency != expected_currency
    ):
        raise PaymentOrderRecoveryError("Recovery evidence does not match the reservation.")
    reservation_id = reservation_ref.id
    contract_id = reservation_ref.contract_id
    reservation_merchant_id = reservation_ref.merchant_id
    await db.rollback()

    try:
        merchant = registry.resolve(reservation_merchant_id)
    except MerchantRegistryError as exc:
        raise PaymentOrderRecoveryError("Recovery merchant is not trusted.") from exc
    try:
        order = await paypal.get_order(
            order_id=provider_order_id,
            expected_paypal_merchant_id=merchant.paypal_merchant_id,
            amount=expected_amount,
            currency=expected_currency,
        )
    except PayPalSandboxError as exc:
        raise PaymentOrderRecoveryError("PayPal order could not be verified.") from exc

    if (
        not isinstance(order, dict)
        or order.get("id") != provider_order_id
        or order.get("status") != "PAYER_ACTION_REQUIRED"
        or _has_capture(order)
    ):
        raise PaymentOrderRecoveryError("PayPal order is not eligible for recovery.")

    # Lock and revalidate in the repository's canonical order. Any state
    # changes while PayPal was being queried invalidate this recovery.
    try:
        async with db.begin():
            current_attempt_ref = await db.get(PaymentAttemptRecord, attempt_id)
            if current_attempt_ref is None:
                raise PaymentOrderRecoveryError("Recovery target is unavailable.")
            contract = await db.scalar(
                select(IntentContractRecord)
                .where(IntentContractRecord.id == contract_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            reservation = await db.scalar(
                select(PaymentReservationRecord)
                .where(PaymentReservationRecord.id == reservation_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            attempt = await db.scalar(
                select(PaymentAttemptRecord)
                .where(PaymentAttemptRecord.id == attempt_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if contract is None or reservation is None or attempt is None:
                raise PaymentOrderRecoveryError("Recovery target is unavailable.")
            approval = await db.scalar(
                select(PaymentCheckoutApprovalRecord)
                .where(PaymentCheckoutApprovalRecord.attempt_id == attempt_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if (
                reservation.contract_id != contract.id
                or reservation.id != expected_reservation_id
                or contract.id != expected_contract_id
                or reservation.contract_version != expected_contract_version
                or reservation.merchant_id != expected_internal_merchant_id
                or reservation.amount != expected_amount
                or reservation.currency != expected_currency
                or contract.status != "APPROVED"
                or contract.owner_id != reservation.actor_id
                or contract.version != reservation.contract_version
                or contract.merchant_id != reservation.merchant_id
                or contract.currency != reservation.currency
                or reservation.amount > contract.maximum_amount
                or reservation.status != "EXECUTION_PENDING"
                or attempt.reservation_id != reservation.id
                or attempt.status != "PENDING"
                or attempt.capture_id is not None
                or attempt.capture_claimed_at is not None
            ):
                raise PaymentOrderRecoveryError("Payment is no longer eligible for recovery.")

            if attempt.provider_order_id is not None:
                if attempt.provider_order_id != provider_order_id:
                    raise PaymentOrderRecoveryError("A different provider order is already bound.")
                prior = await db.scalar(
                    select(PaymentAttemptEventRecord.id).where(
                        PaymentAttemptEventRecord.attempt_id == attempt_id,
                        PaymentAttemptEventRecord.event_type == "ORDER_CREATE_RECOVERED",
                        PaymentAttemptEventRecord.event_data["provider_order_id"].astext
                        == provider_order_id,
                    )
                )
                # The binding is already durable. Never rewrite it or emit a
                # second recovery event, regardless of its original source.
                del prior
                return PaymentOrderRecoveryResult(attempt_id, provider_order_id, False)

            if approval is not None:
                raise PaymentOrderRecoveryError("Checkout approval already exists.")

            conflict = await db.scalar(
                select(PaymentAttemptRecord.id).where(
                    PaymentAttemptRecord.provider_order_id == provider_order_id,
                    PaymentAttemptRecord.id != attempt_id,
                )
            )
            if conflict is not None:
                raise PaymentOrderRecoveryError("Provider order is already bound elsewhere.")

            attempt.provider_order_id = provider_order_id
            db.add(PaymentAttemptEventRecord(
                attempt_id=attempt_id,
                actor_id=None,
                event_type="ORDER_CREATE_RECOVERED",
                event_correlation_id=uuid.uuid4(),
                event_data={
                    "category": "OPERATOR_VERIFIED_PROVIDER_ORDER_RECOVERY",
                    "provider_order_id": provider_order_id,
                    "provider_status": "PAYER_ACTION_REQUIRED",
                    "merchant_id": merchant.paypal_merchant_id,
                    "amount": str(expected_amount),
                    "currency": expected_currency,
                    "evidence_source": "PAYPAL_DEVELOPER_DASHBOARD_RETURN_CANCEL_CORRELATION",
                    "correlated_attempt_id": str(dashboard_correlation_attempt_id),
                },
            ))
            await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise PaymentOrderRecoveryError("Recovery conflicted with another payment operation.") from exc

    return PaymentOrderRecoveryResult(attempt_id, provider_order_id, True)
