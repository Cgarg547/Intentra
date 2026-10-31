import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from intentra.database import get_db
from intentra.models.intent_contract import (
    IntentContractRecord,
    UserRecord,
)
from intentra.models.payment_evaluation import PaymentEvaluationRecord
from intentra.models.payment_reservation import PaymentReservationRecord
from intentra.routes.auth import current_user
from intentra.schemas.payments import (
    PaymentEvaluationRequest,
    PaymentEvaluationResponse,
    PaymentEvaluationHistoryItem,
    PaymentEvaluationHistoryResponse,
    PaymentReservationRequest,
    PaymentReservationResponse,
)
from intentra.services.authorization import (
    IntentContract,
    PaymentProposal,
    authorize,
)

router = APIRouter(prefix="/api/payments", tags=["Payments"])


@router.post(
    "/evaluate",
    response_model=PaymentEvaluationResponse,
)
async def evaluate_payment(
    payload: PaymentEvaluationRequest,
    user: UserRecord = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    actor_id = user.id

    contract = await db.scalar(
        select(IntentContractRecord).where(
            IntentContractRecord.id == payload.contract_id,
            IntentContractRecord.owner_id == actor_id,
        )
    )

    if contract is None:
        raise HTTPException(
            status_code=404,
            detail="Contract not found",
        )

    result = authorize(
        IntentContract(
            merchant_id=contract.merchant_id,
            maximum_amount=contract.maximum_amount,
            currency=contract.currency,
            approved=contract.status == "APPROVED",
        ),
        PaymentProposal(
            merchant_id=payload.merchant_id,
            amount=payload.amount,
            currency=payload.currency,
        ),
    )

    evaluation = PaymentEvaluationRecord(
        contract_id=contract.id,
        actor_id=actor_id,
        contract_version=contract.version,
        merchant_id=payload.merchant_id,
        amount=payload.amount,
        currency=payload.currency,
        decision=result.decision.value,
        reason=result.reason,
    )

    db.add(evaluation)
    await db.commit()
    await db.refresh(evaluation)

    return PaymentEvaluationResponse(
        evaluation_id=evaluation.id,
        contract_id=contract.id,
        contract_version=contract.version,
        decision=evaluation.decision,
        reason=evaluation.reason,
    )


@router.get(
    "/evaluations",
    response_model=PaymentEvaluationHistoryResponse,
)
async def list_payment_evaluations(
    contract_id: uuid.UUID,
    user: UserRecord = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    contract = await db.scalar(
        select(IntentContractRecord).where(
            IntentContractRecord.id == contract_id,
            IntentContractRecord.owner_id == user.id,
        )
    )

    if contract is None:
        raise HTTPException(
            status_code=404,
            detail="Contract not found",
        )

    evaluations = (
        await db.scalars(
            select(PaymentEvaluationRecord)
            .where(
                PaymentEvaluationRecord.contract_id == contract_id,
                PaymentEvaluationRecord.actor_id == user.id,
            )
            .order_by(
                PaymentEvaluationRecord.created_at.desc(),
                PaymentEvaluationRecord.id.desc(),
            )
            .limit(100)
        )
    ).all()

    return PaymentEvaluationHistoryResponse(
        items=[
            PaymentEvaluationHistoryItem(
                evaluation_id=record.id,
                contract_id=record.contract_id,
                contract_version=record.contract_version,
                merchant_id=record.merchant_id,
                amount=record.amount,
                currency=record.currency,
                decision=record.decision,
                reason=record.reason,
                created_at=record.created_at,
            )
            for record in evaluations
        ]
    )


@router.post(
    "/reserve",
    response_model=PaymentReservationResponse,
)
async def reserve_payment(
    payload: PaymentReservationRequest,
    user: UserRecord = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    actor_id = user.id

    # Serialize reservations and revocation against this contract.
    contract = await db.scalar(
        select(IntentContractRecord)
        .where(
            IntentContractRecord.id == payload.contract_id,
            IntentContractRecord.owner_id == actor_id,
        )
        .with_for_update()
    )

    if contract is None:
        raise HTTPException(status_code=404, detail="Contract not found")

    spent = await db.scalar(
        select(func.coalesce(func.sum(PaymentReservationRecord.amount), 0))
        .where(
            PaymentReservationRecord.contract_id == contract.id,
            PaymentReservationRecord.status == "RESERVED",
        )
    )
    remaining = contract.maximum_amount - spent

    existing = await db.scalar(
        select(PaymentReservationRecord).where(
            PaymentReservationRecord.contract_id == contract.id,
            PaymentReservationRecord.idempotency_key
            == payload.idempotency_key,
        )
    )

    if existing is not None:
        if (
            existing.merchant_id != payload.merchant_id
            or existing.amount != payload.amount
            or existing.currency != payload.currency
        ):
            raise HTTPException(
                status_code=409,
                detail="Idempotency key reused with different payment details",
            )

        return PaymentReservationResponse(
            reservation_id=existing.id,
            contract_id=existing.contract_id,
            contract_version=existing.contract_version,
            status=existing.status,
            reason=existing.reason,
            remaining_amount=remaining,
        )

    result = authorize(
        IntentContract(
            merchant_id=contract.merchant_id,
            maximum_amount=contract.maximum_amount,
            currency=contract.currency,
            approved=contract.status == "APPROVED",
        ),
        PaymentProposal(
            merchant_id=payload.merchant_id,
            amount=payload.amount,
            currency=payload.currency,
        ),
    )

    if result.decision.value != "ALLOW":
        reservation_status = "BLOCKED"
        reason = result.reason
    elif payload.amount > remaining:
        reservation_status = "BLOCKED"
        reason = "Payment exceeds the remaining authorized budget."
    else:
        reservation_status = "RESERVED"
        reason = "Payment budget reserved successfully."
        remaining -= payload.amount

    reservation = PaymentReservationRecord(
        contract_id=contract.id,
        actor_id=actor_id,
        contract_version=contract.version,
        idempotency_key=payload.idempotency_key,
        merchant_id=payload.merchant_id,
        amount=payload.amount,
        currency=payload.currency,
        status=reservation_status,
        reason=reason,
    )

    db.add(reservation)
    await db.commit()
    await db.refresh(reservation)

    return PaymentReservationResponse(
        reservation_id=reservation.id,
        contract_id=reservation.contract_id,
        contract_version=reservation.contract_version,
        status=reservation.status,
        reason=reservation.reason,
        remaining_amount=remaining,
    )
