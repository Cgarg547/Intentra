import uuid
from sqlalchemy import update, func
from intentra.schemas.contracts import ContractApprovalRequest
from sqlalchemy import select
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from intentra.schemas.contracts import ContractRevocationRequest

from intentra.database import get_db
from intentra.models.intent_contract import (
    AuditEventRecord,
    IntentContractRecord,
    UserRecord,
)
from intentra.routes.auth import current_user
from intentra.schemas.contracts import ContractCreate, ContractResponse

router = APIRouter(prefix="/api/contracts", tags=["Intent Contracts"])


@router.post(
    "",
    response_model=ContractResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_contract(
    payload: ContractCreate,
    user: UserRecord = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    contract = IntentContractRecord(
        owner_id=user.id,
        merchant_id=payload.merchant_id,
        maximum_amount=payload.maximum_amount,
        currency=payload.currency,
        status="DRAFT",
        version=1,
    )

    db.add(contract)
    await db.flush()

    db.add(
        AuditEventRecord(
            contract_id=contract.id,
            actor_id=user.id,
            event_type="CONTRACT_CREATED",
            contract_version=1,
            event_data={
                "merchant_id": payload.merchant_id,
                "maximum_amount": str(payload.maximum_amount),
                "currency": payload.currency,
                "status": "DRAFT",
            },
        )
    )

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Unable to create contract",
        )

    await db.refresh(contract)
    return contract


@router.get("/{contract_id}", response_model=ContractResponse)
async def get_contract(
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

    return contract


@router.post(
    "/{contract_id}/approve",
    response_model=ContractResponse,
)
async def approve_contract(
    contract_id: uuid.UUID,
    payload: ContractApprovalRequest,
    user: UserRecord = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    actor_id = user.id

    result = await db.execute(
        update(IntentContractRecord)
        .where(
            IntentContractRecord.id == contract_id,
            IntentContractRecord.owner_id == actor_id,
            IntentContractRecord.status == "DRAFT",
            IntentContractRecord.version == payload.expected_version,
        )
        .values(
            status="APPROVED",
            approved_by=actor_id,
            approved_at=func.now(),
            version=IntentContractRecord.version + 1,
        )
        .returning(IntentContractRecord)
    )

    contract = result.scalar_one_or_none()

    if contract is None:
        await db.rollback()

        existing = await db.scalar(
            select(IntentContractRecord).where(
                IntentContractRecord.id == contract_id,
                IntentContractRecord.owner_id == actor_id,
            )
        )

        if existing is None:
            raise HTTPException(status_code=404, detail="Contract not found")

        raise HTTPException(
            status_code=409,
            detail="Contract state or version conflict",
        )

    db.add(
        AuditEventRecord(
            contract_id=contract.id,
            actor_id=actor_id,
            event_type="CONTRACT_APPROVED",
            contract_version=contract.version,
            event_data={
                "previous_status": "DRAFT",
                "new_status": "APPROVED",
                "expected_version": payload.expected_version,
            },
        )
    )

    await db.commit()
    await db.refresh(contract)

    return contract


@router.post(
    "/{contract_id}/revoke",
    response_model=ContractResponse,
)
async def revoke_contract(
    contract_id: uuid.UUID,
    payload: ContractRevocationRequest,
    user: UserRecord = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    actor_id = user.id

    result = await db.execute(
        update(IntentContractRecord)
        .where(
            IntentContractRecord.id == contract_id,
            IntentContractRecord.owner_id == actor_id,
            IntentContractRecord.status == "APPROVED",
            IntentContractRecord.version == payload.expected_version,
        )
        .values(
            status="REVOKED",
            revoked_at=func.now(),
            version=IntentContractRecord.version + 1,
        )
        .returning(IntentContractRecord)
    )

    contract = result.scalar_one_or_none()

    if contract is None:
        await db.rollback()

        existing = await db.scalar(
            select(IntentContractRecord).where(
                IntentContractRecord.id == contract_id,
                IntentContractRecord.owner_id == actor_id,
            )
        )

        if existing is None:
            raise HTTPException(
                status_code=404,
                detail="Contract not found",
            )

        raise HTTPException(
            status_code=409,
            detail="Contract state or version conflict",
        )

    db.add(
        AuditEventRecord(
            contract_id=contract.id,
            actor_id=actor_id,
            event_type="CONTRACT_REVOKED",
            contract_version=contract.version,
            event_data={
                "previous_status": "APPROVED",
                "new_status": "REVOKED",
                "expected_version": payload.expected_version,
            },
        )
    )

    await db.commit()
    await db.refresh(contract)

    return contract
