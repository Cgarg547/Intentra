import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from intentra.models.intent_contract import IntentContractRecord
from intentra.models.payment_attempt import PaymentAttemptRecord
from intentra.models.payment_reservation import PaymentReservationRecord
from intentra.services.payment_reconciliation_evidence import (
    record_reconciliation_evidence,
)


class ReconciliationFinalizeError(Exception):
    pass


async def finalize_reconciliation_evidence(
    db: AsyncSession,
    *,
    operation_id: uuid.UUID,
    attempt_id: uuid.UUID,
    expected_snapshot: tuple,
    event_type: str,
    provider_order_id: str | None,
    provider_status: str | None,
    evidence_data: dict,
):
    """
    Revalidate payment state and persist reconciliation evidence.

    Caller must supply a session without an active transaction.
    Does not create/capture payments or change payment state.
    """
    if db.in_transaction():
        raise ReconciliationFinalizeError(
            "Finalization requires a session without an active transaction."
        )

    # Read relationship IDs before locking.
    async with db.begin():
        attempt_ref = await db.get(PaymentAttemptRecord, attempt_id)
        if attempt_ref is None:
            raise ReconciliationFinalizeError(
                "Payment attempt not found."
            )

        reservation_ref = await db.get(
            PaymentReservationRecord,
            attempt_ref.reservation_id,
        )
        if reservation_ref is None:
            raise ReconciliationFinalizeError(
                "Payment reservation not found."
            )

        contract_id = reservation_ref.contract_id
        reservation_id = reservation_ref.id

    db.expire_all()

    async with db.begin():
        contract = await db.scalar(
            select(IntentContractRecord)
            .where(IntentContractRecord.id == contract_id)
            .with_for_update()
        )

        if contract is None:
            raise ReconciliationFinalizeError(
                "Payment state changed during reconciliation."
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

        if reservation is None or attempt is None:
            raise ReconciliationFinalizeError(
                "Payment state changed during reconciliation."
            )

        if (
            reservation.contract_id != contract.id
            or attempt.reservation_id != reservation.id
        ):
            raise ReconciliationFinalizeError(
                "Payment relationships changed during reconciliation."
            )

        current_snapshot = (
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

        if current_snapshot != expected_snapshot:
            raise ReconciliationFinalizeError(
                "Payment state changed during reconciliation."
            )

        result = await record_reconciliation_evidence(
            db,
            operation_id=operation_id,
            attempt_id=attempt_id,
            event_type=event_type,
            provider_order_id=provider_order_id,
            provider_status=provider_status,
            evidence_data=evidence_data,
        )

    return result
