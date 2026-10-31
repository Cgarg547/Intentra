import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from intentra.models.payment_attempt import PaymentAttemptRecord
from intentra.models.payment_reservation import PaymentReservationRecord
from intentra.services.merchant_registry import TrustedMerchantRegistry
from intentra.services.payment_reconciliation import (
    PaymentReconciliationError,
    plan_order_reconciliation,
)
from intentra.services.paypal_sandbox import PayPalSandboxClient


@dataclass(frozen=True)
class ReconciliationResult:
    attempt_id: uuid.UUID
    action: str
    provider_order_id: str | None
    provider_status: str | None


async def reconcile_payment_attempt(
    db: AsyncSession,
    *,
    attempt_id: uuid.UUID,
    registry: TrustedMerchantRegistry,
    paypal: PayPalSandboxClient,
) -> ReconciliationResult:
    """
    Read-only reconciliation of an existing payment attempt.

    The caller must provide a dedicated session with no active
    transaction. This function manages its own read transactions.

    Never creates or captures payments or changes budget.
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
        return ReconciliationResult(
            attempt_id=attempt_id,
            action="HOLD_FOR_REVIEW",
            provider_order_id=None,
            provider_status=None,
        )

    merchant = registry.resolve(snapshot[7])

    # No database transaction is held during external HTTP.
    order = await paypal.get_order(
        order_id=decision.provider_order_id,
        expected_paypal_merchant_id=merchant.paypal_merchant_id,
        amount=snapshot[8],
        currency=snapshot[9],
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
