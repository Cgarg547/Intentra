"""Shared deterministic budget evaluation and reservation primitives.

Callers must lock the contract row first and own the surrounding transaction.
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from intentra.models.intent_contract import IntentContractRecord
from intentra.models.payment_reservation import PaymentReservationRecord
from intentra.services.authorization import IntentContract, PaymentProposal, authorize

ACTIVE_BUDGET_STATUSES = ("RESERVED", "EXECUTION_PENDING", "OUTCOME_UNKNOWN", "CAPTURED")


class PaymentReservationError(Exception):
    def __init__(self, message: str, status_code: int = 409):
        self.status_code = status_code
        super().__init__(message)


@dataclass(frozen=True)
class ReservationEvaluation:
    decision: str
    reason: str
    remaining_amount: Decimal


async def evaluate_contract_payment(
    db: AsyncSession,
    *,
    contract: IntentContractRecord,
    merchant_id: str,
    amount: Decimal,
    currency: str,
) -> ReservationEvaluation:
    """Evaluate authorization and live available budget for a locked contract."""
    spent = await db.scalar(
        select(func.coalesce(func.sum(PaymentReservationRecord.amount), 0)).where(
            PaymentReservationRecord.contract_id == contract.id,
            PaymentReservationRecord.status.in_(ACTIVE_BUDGET_STATUSES),
        )
    )
    remaining = contract.maximum_amount - Decimal(spent or 0)
    result = authorize(
        IntentContract(
            merchant_id=contract.merchant_id,
            maximum_amount=contract.maximum_amount,
            currency=contract.currency,
            approved=contract.status == "APPROVED",
        ),
        PaymentProposal(merchant_id=merchant_id, amount=amount, currency=currency),
    )
    if result.decision.value != "ALLOW":
        return ReservationEvaluation("BLOCK", result.reason, remaining)
    if amount > remaining:
        return ReservationEvaluation("BLOCK", "Payment exceeds the remaining authorized budget.", remaining)
    return ReservationEvaluation("ALLOW", "Payment budget reserved successfully.", remaining)


async def reserve_payment_locked(
    db: AsyncSession,
    *,
    contract: IntentContractRecord,
    actor_id: uuid.UUID,
    idempotency_key: str,
    merchant_id: str,
    amount: Decimal,
    currency: str,
    require_allow: bool = False,
) -> tuple[PaymentReservationRecord, Decimal, bool]:
    """Create or retrieve an idempotent reservation while the contract is locked."""
    existing = await db.scalar(
        select(PaymentReservationRecord).where(
            PaymentReservationRecord.contract_id == contract.id,
            PaymentReservationRecord.idempotency_key == idempotency_key,
        )
    )
    evaluation = await evaluate_contract_payment(
        db, contract=contract, merchant_id=merchant_id, amount=amount, currency=currency
    )
    if existing is not None:
        if (existing.actor_id != actor_id or existing.merchant_id != merchant_id
            or existing.amount != amount or existing.currency != currency):
            raise PaymentReservationError("Idempotency key reused with different payment details.")
        return existing, evaluation.remaining_amount, False

    if require_allow and evaluation.decision != "ALLOW":
        raise PaymentReservationError(evaluation.reason)
    status = "RESERVED" if evaluation.decision == "ALLOW" else "BLOCKED"
    reason = evaluation.reason
    remaining = evaluation.remaining_amount
    if status == "RESERVED":
        remaining -= amount
    reservation = PaymentReservationRecord(
        contract_id=contract.id,
        actor_id=actor_id,
        contract_version=contract.version,
        idempotency_key=idempotency_key,
        merchant_id=merchant_id,
        amount=amount,
        currency=currency,
        status=status,
        reason=reason,
    )
    db.add(reservation)
    await db.flush()
    return reservation, remaining, True
