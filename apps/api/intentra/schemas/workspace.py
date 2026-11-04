import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class AuditEventItem(BaseModel):
    event_id: uuid.UUID
    correlation_id: uuid.UUID | None = None
    entity_type: str
    entity_id: uuid.UUID
    related_ids: dict[str, uuid.UUID] = Field(default_factory=dict)
    actor_id: uuid.UUID | None = None
    actor_email: str | None = None
    event_type: str
    event_data: dict
    created_at: datetime


class AuditEventPage(BaseModel):
    items: list[AuditEventItem]
    limit: int
    offset: int
    next_offset: int | None


class MerchantItem(BaseModel):
    internal_merchant_id: str
    paypal_merchant_id: str
    trust_source: str = "server_configuration"
    provider_live_verified: bool = False


class MerchantList(BaseModel):
    items: list[MerchantItem]
    configured: bool


class SecuritySummary(BaseModel):
    authenticated: bool
    active_session_count: int
    current_session_valid: bool
    contracts: dict[str, int]
    trusted_merchant_count: int
    payment_states: dict[str, int]
    policy_decisions: dict[str, int]
    unresolved_attempts: int
    generated_at: datetime


class AnalyticsSummary(BaseModel):
    payments: dict[str, int]
    payment_states: list[dict]
    budget_by_contract: list[dict]
    captured_by_merchant: list[dict]
    policy_decisions: dict[str, int]
    proposals: dict[str, int]
    daily_captured: list[dict]
    transactions: list[dict]


class SystemStatus(BaseModel):
    api: str
    database: str
    paypal_sandbox: str
    trusted_merchants: str
    llm_mode: str
    llm_provider: str
    llm_runtime: str
    llm_model_status: str
    checked_at: datetime
