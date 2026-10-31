import uuid
from decimal import Decimal

from pydantic import BaseModel, Field


class PaymentEvaluationRequest(BaseModel):
    contract_id: uuid.UUID
    merchant_id: str = Field(min_length=1, max_length=128)
    amount: Decimal = Field(
        gt=0,
        max_digits=18,
        decimal_places=2,
        allow_inf_nan=False,
    )
    currency: str = Field(pattern=r"^[A-Z]{3}$")


class PaymentEvaluationResponse(BaseModel):
    evaluation_id: uuid.UUID
    contract_id: uuid.UUID
    contract_version: int
    decision: str
    reason: str


from datetime import datetime


class PaymentEvaluationHistoryItem(BaseModel):
    evaluation_id: uuid.UUID
    contract_id: uuid.UUID
    contract_version: int
    merchant_id: str
    amount: Decimal
    currency: str
    decision: str
    reason: str
    created_at: datetime


class PaymentEvaluationHistoryResponse(BaseModel):
    items: list[PaymentEvaluationHistoryItem]


class PaymentReservationRequest(BaseModel):
    contract_id: uuid.UUID
    idempotency_key: str = Field(min_length=1, max_length=128)
    merchant_id: str = Field(min_length=1, max_length=128)
    amount: Decimal = Field(
        gt=0,
        max_digits=18,
        decimal_places=2,
        allow_inf_nan=False,
    )
    currency: str = Field(pattern=r"^[A-Z]{3}$")


class PaymentReservationResponse(BaseModel):
    reservation_id: uuid.UUID
    contract_id: uuid.UUID
    contract_version: int
    status: str
    reason: str
    remaining_amount: Decimal
