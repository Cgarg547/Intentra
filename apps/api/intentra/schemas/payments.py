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


class CheckoutApprovalRequest(BaseModel):
    attempt_id: uuid.UUID


class CheckoutReturnRequest(BaseModel):
    attempt_id: uuid.UUID
    state: str = Field(min_length=32, max_length=128)


class CheckoutApprovalResponse(BaseModel):
    approval_id: uuid.UUID
    attempt_id: uuid.UUID
    provider_order_id: str
    return_state: str | None = None
    expires_at: datetime
    state: str


class PaymentCheckoutLaunchResponse(CheckoutApprovalResponse):
    approval_url: str


class PaymentAttemptHistoryItem(BaseModel):
    attempt_id: uuid.UUID
    reservation_id: uuid.UUID
    contract_id: uuid.UUID
    provider_order_id: str | None
    capture_id: str | None
    attempt_state: str
    reservation_state: str
    approval_state: str | None
    approval_expires_at: datetime | None
    approval_consumed_at: datetime | None
    merchant_id: str
    amount: Decimal
    currency: str
    created_at: datetime
    updated_at: datetime


class PaymentAttemptHistoryResponse(BaseModel):
    items: list[PaymentAttemptHistoryItem]


class PaymentReservationHistoryItem(BaseModel):
    reservation_id: uuid.UUID
    contract_id: uuid.UUID
    merchant_id: str
    amount: Decimal
    currency: str
    status: str
    reason: str
    created_at: datetime


class PaymentReservationHistoryResponse(BaseModel):
    items: list[PaymentReservationHistoryItem]


class PaymentAttemptEventItem(BaseModel):
    event_type: str
    event_correlation_id: uuid.UUID
    event_data: dict
    created_at: datetime


class PaymentAttemptDetailResponse(PaymentAttemptHistoryItem):
    approval_verified_at: datetime | None = None
    events: list[PaymentAttemptEventItem] = Field(default_factory=list)


class CheckoutVerificationResponse(BaseModel):
    approval_id: uuid.UUID
    attempt_id: uuid.UUID
    state: str
    verified_at: datetime | None


class PaymentCaptureResponse(BaseModel):
    attempt_id: uuid.UUID
    state: str
    capture_id: str | None
    action: str


class PaymentReconciliationResponse(BaseModel):
    attempt_id: uuid.UUID
    action: str
    provider_order_id: str | None
    provider_status: str | None
    capture_id: str | None = None
