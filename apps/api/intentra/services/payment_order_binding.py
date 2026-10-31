import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
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

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()

        # PostgreSQL SQLSTATE 23505 indicates a unique violation.
        # Translate only our provider-order constraint.
        original = exc.orig
        sqlstate = getattr(original, "sqlstate", None)
        if sqlstate is None:
            sqlstate = getattr(
                getattr(original, "__cause__", None),
                "sqlstate",
                None,
            )

        constraint_name = getattr(
            original,
            "constraint_name",
            None,
        )
        if constraint_name is None:
            constraint_name = getattr(
                getattr(original, "__cause__", None),
                "constraint_name",
                None,
            )

        if (
            sqlstate == "23505"
            and (
                constraint_name == "uq_payment_attempt_provider_order"
                or (
                    constraint_name is None
                    and "uq_payment_attempt_provider_order"
                    in str(original)
                )
            )
        ):
            raise PaymentOrderBindingError(
                "Provider order ID is already bound."
            ) from exc

        raise

    return PaymentOrderBinding(
        attempt_id=attempt.id,
        reservation_id=reservation.id,
        provider_order_id=provider_order_id,
        changed=True,
    )
