import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from intentra.models.intent_contract import IntentContractRecord
from intentra.models.payment_attempt import PaymentAttemptRecord
from intentra.models.payment_reservation import PaymentReservationRecord


class ExecutionClaimError(Exception):
    pass


@dataclass(frozen=True)
class ExecutionClaim:
    attempt_id: uuid.UUID
    reservation_id: uuid.UUID
    provider_idempotency_key: str
    status: str
    newly_claimed: bool


async def claim_payment_execution(
    db: AsyncSession,
    *,
    reservation_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> ExecutionClaim:
    # The contract lock serializes claims against contract revocation.
    # Every execution claim must acquire this lock first.
    reservation = await db.scalar(
        select(PaymentReservationRecord).where(
            PaymentReservationRecord.id == reservation_id,
            PaymentReservationRecord.actor_id == actor_id,
        )
    )

    if reservation is None:
        raise ExecutionClaimError("Reservation not found.")

    contract = await db.scalar(
        select(IntentContractRecord)
        .where(
            IntentContractRecord.id == reservation.contract_id,
            IntentContractRecord.owner_id == actor_id,
        )
        .with_for_update()
    )

    if contract is None:
        raise ExecutionClaimError("Contract not found.")

    # Reload and lock the reservation after acquiring the contract lock.
    reservation = await db.scalar(
        select(PaymentReservationRecord)
        .where(
            PaymentReservationRecord.id == reservation_id,
            PaymentReservationRecord.actor_id == actor_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )

    if reservation is None:
        raise ExecutionClaimError("Reservation not found.")

    existing = await db.scalar(
        select(PaymentAttemptRecord).where(
            PaymentAttemptRecord.reservation_id == reservation.id
        )
    )

    if existing is not None:
        return ExecutionClaim(
            attempt_id=existing.id,
            reservation_id=reservation.id,
            provider_idempotency_key=existing.provider_idempotency_key,
            status=existing.status,
            newly_claimed=False,
        )

    if contract.status != "APPROVED":
        raise ExecutionClaimError("Contract is not approved.")

    if reservation.status != "RESERVED":
        raise ExecutionClaimError("Reservation is not executable.")

    if (
        reservation.merchant_id != contract.merchant_id
        or reservation.currency != contract.currency
    ):
        raise ExecutionClaimError("Reservation does not match contract.")

    if reservation.contract_version != contract.version:
        raise ExecutionClaimError("Reservation contract version is stale.")

    if (
        reservation.amount <= 0
        or reservation.amount > contract.maximum_amount
    ):
        raise ExecutionClaimError("Reservation amount is unauthorized.")

    provider_key = f"intentra-{reservation.id}"

    attempt = PaymentAttemptRecord(
        reservation_id=reservation.id,
        provider_idempotency_key=provider_key,
        status="PENDING",
    )

    reservation.status = "EXECUTION_PENDING"
    reservation.reason = "Payment execution claimed."

    db.add(attempt)
    await db.flush()

    result = ExecutionClaim(
        attempt_id=attempt.id,
        reservation_id=reservation.id,
        provider_idempotency_key=provider_key,
        status=attempt.status,
        newly_claimed=True,
    )

    await db.commit()
    return result
