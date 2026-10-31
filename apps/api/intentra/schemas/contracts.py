import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ContractCreate(BaseModel):
    merchant_id: str = Field(
        min_length=1,
        max_length=128,
    )
    maximum_amount: Decimal = Field(
        gt=0,
        max_digits=18,
        decimal_places=2,
    )
    currency: str = Field(
        pattern=r"^[A-Z]{3}$",
    )


class ContractResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID | None
    merchant_id: str
    maximum_amount: Decimal
    currency: str
    status: str
    version: int
    created_at: datetime
    approved_at: datetime | None
    approved_by: uuid.UUID | None
    revoked_at: datetime | None


class ContractApprovalRequest(BaseModel):
    expected_version: int = Field(ge=1)


class ContractRevocationRequest(BaseModel):
    expected_version: int = Field(ge=1)
