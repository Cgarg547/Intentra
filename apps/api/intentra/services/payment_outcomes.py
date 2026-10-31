import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from intentra.models.intent_contract import IntentContractRecord
from intentra.models.payment_attempt import PaymentAttemptRecord
from intentra.models.payment_reservation import PaymentReservationRecord


class PaymentOutcomeError(Exception):
    pass


@dataclass(frozen=True)
class PaymentOutcome:
    attempt_id: uuid.UUID
    reservation_id: uuid.UUID
    attempt_status: str
    reservation_status: str
    changed: bool


TARGETS = {
    "SUCCEEDED": "CAPTURED",
    "FAILED": "CANCELLED",
    "UNKNOWN": "OUTCOME_UNKNOWN",
}

ALLOWED = {
    "PENDING": {"SUCCEEDED", "FAILED", "UNKNOWN"},
    "UNKNOWN": {"SUCCEEDED", "FAILED"},
    "SUCCEEDED": set(),
    "FAILED": set(),
}


async def record_payment_outcome(
    db: AsyncSession,
    *,
    attempt_id: uuid.UUID,
    outcome: str,
) -> PaymentOutcome:
    """
    Internal trusted-provider/reconciliation service only.

    Callers must authenticate and verify provider evidence before
    invoking this function. Never expose it directly to a user API.
    """
    if outcome not in TARGETS:
        raise PaymentOutcomeError("Unsupported payment outcome.")

    # Read IDs first, then acquire locks in contract -> reservation
    # -> attempt order, consistent with reservation/execution flows.
    attempt_ref = await db.scalar(
        select(PaymentAttemptRecord).where(
            PaymentAttemptRecord.id == attempt_id
        )
    )
    if attempt_ref is None:
        raise PaymentOutcomeError("Payment attempt not found.")

    reservation_ref = await db.scalar(
        select(PaymentReservationRecord).where(
            PaymentReservationRecord.id == attempt_ref.reservation_id
        )
    )
    if reservation_ref is None:
        raise PaymentOutcomeError("Payment reservation not found.")

    contract = await db.scalar(
        select(IntentContractRecord)
        .where(IntentContractRecord.id == reservation_ref.contract_id)
        .with_for_update()
    )
    if contract is None:
        raise PaymentOutcomeError("Intent contract not found.")

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
        raise PaymentOutcomeError("Payment record not found.")

    if attempt.reservation_id != reservation.id:
        raise PaymentOutcomeError("Payment record relationship changed.")

    target_reservation_status = TARGETS[outcome]

    if attempt.status == outcome:
        if reservation.status != target_reservation_status:
            raise PaymentOutcomeError("Inconsistent payment state.")
        return PaymentOutcome(
            attempt_id=attempt.id,
            reservation_id=reservation.id,
            attempt_status=attempt.status,
            reservation_status=reservation.status,
            changed=False,
        )

    if outcome not in ALLOWED.get(attempt.status, set()):
        raise PaymentOutcomeError("Conflicting payment outcome.")

    expected_reservation_status = {
        "PENDING": "EXECUTION_PENDING",
        "UNKNOWN": "OUTCOME_UNKNOWN",
    }.get(attempt.status)

    if reservation.status != expected_reservation_status:
        raise PaymentOutcomeError("Unexpected reservation state.")

    attempt.status = outcome
    reservation.status = target_reservation_status
    reservation.reason = {
        "SUCCEEDED": "Provider-confirmed payment success.",
        "FAILED": "Provider-confirmed no charge occurred.",
        "UNKNOWN": "Payment outcome requires reconciliation.",
    }[outcome]

    await db.commit()

    return PaymentOutcome(
        attempt_id=attempt.id,
        reservation_id=reservation.id,
        attempt_status=attempt.status,
        reservation_status=reservation.status,
        changed=True,
    )
