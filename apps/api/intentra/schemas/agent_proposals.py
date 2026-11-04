import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProposalCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    request: str = Field(min_length=1, max_length=4000)
    contract_id: uuid.UUID | None = None

    @field_validator("request")
    @classmethod
    def request_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("request cannot be blank")
        return value


class ProposalRejectRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)

    @field_validator("reason")
    @classmethod
    def reason_not_blank(cls, value):
        if value is not None and not value.strip():
            raise ValueError("rejection reason cannot be blank")
        return value.strip() if value is not None else None


class ProposalEventResponse(BaseModel):
    event_type: str
    actor_id: uuid.UUID | None = None
    event_data: dict
    created_at: datetime


class PaymentPreparationResponse(BaseModel):
    reservation_id: uuid.UUID
    attempt_id: uuid.UUID
    contract_version: int
    created_at: datetime
    status: str


class ProposalResponse(BaseModel):
    proposal_id: uuid.UUID
    owner_id: uuid.UUID
    request: str
    requested_purpose: str | None
    merchant_id: str | None
    proposed_amount: Decimal | None
    currency: str | None
    contract_id: uuid.UUID | None
    contract_version: int | None
    explanation: str
    missing_information: list[str]
    policy_decision: str | None
    policy_reason: str | None
    status: str
    provider_mode: str
    version: int
    created_at: datetime
    updated_at: datetime
    payment_preparation: PaymentPreparationResponse | None = None
    events: list[ProposalEventResponse] = Field(default_factory=list)


class ProposalListResponse(BaseModel):
    items: list[ProposalResponse]
