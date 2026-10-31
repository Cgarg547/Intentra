import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from intentra.models.intent_contract import IntentContractRecord
from intentra.models.payment_attempt import PaymentAttemptRecord
from intentra.models.payment_reservation import PaymentReservationRecord


class PaymentOrderBindingError(Exception):
    pass


@dataclass(frozen=True)
class PaymentOrderBinding:
    attempt_id: uuid.UUID
    reservation_id: uuid.UUID
    provider_order_id: str
    changed: bool


async def bind_provider_order(
    db: AsyncSession,
    *,
    attempt_id: uuid.UUID,
    provider_order_id: str,
) -> PaymentOrderBinding:
    """
    Internal persistence operation only.

    Callers must verify the provider order and authorized
    merchant, amount, and currency before invoking this service.

    This function does not authorize or execute a payment.
    """
    if (
        not isinstance(provider_order_id, str)
        or not provider_order_id.strip()
        or len(provider_order_id) > 128
        or provider_order_id != provider_order_id.strip()
    ):
        raise PaymentOrderBindingError("Invalid provider order ID.")

    attempt_ref = await db.scalar(
        select(PaymentAttemptRecord).where(
            PaymentAttemptRecord.id == attempt_id
        )
    )

    if attempt_ref is None:
        raise PaymentOrderBindingError("Payment attempt not found.")

    reservation_ref = await db.scalar(
        select(PaymentReservationRecord).where(
            PaymentReservationRecord.id == attempt_ref.reservation_id
        )
    )

    if reservation_ref is None:
        raise PaymentOrderBindingError("Payment reservation not found.")

    # Preserve the established lock ordering.
    contract = await db.scalar(
        select(IntentContractRecord)
        .where(IntentContractRecord.id == reservation_ref.contract_id)
        .with_for_update()
    )

    if contract is None:
        raise PaymentOrderBindingError("Intent contract not found.")

    reservation = await db.scalar(
        select(PaymentReservationRecord)
        .where(PaymentReservationRecord.id == attempt_ref.reservation_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )

    attempt = await db.scalar(
        select(PaymentAttemptRecord)
        .where(PaymentAttemptRecord.id == attempt_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )

    if reservation is None or attempt is None:
        raise PaymentOrderBindingError("Payment record not found.")

    if attempt.reservation_id != reservation.id:
        raise PaymentOrderBindingError("Payment relationship changed.")

    if attempt.provider_order_id is not None:
        if attempt.provider_order_id != provider_order_id:
            raise PaymentOrderBindingError(
                "Conflicting provider order ID."
            )

        return PaymentOrderBinding(
            attempt_id=attempt.id,
            reservation_id=reservation.id,
            provider_order_id=attempt.provider_order_id,
            changed=False,
        )

    if (
        attempt.status != "PENDING"
        or reservation.status != "EXECUTION_PENDING"
    ):
        raise PaymentOrderBindingError(
            "Payment attempt is not eligible for order binding."
        )

    attempt.provider_order_id = provider_order_id

    await db.commit()

    return PaymentOrderBinding(
        attempt_id=attempt.id,
        reservation_id=reservation.id,
        provider_order_id=provider_order_id,
        changed=True,
    )
