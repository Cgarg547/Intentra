import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from intentra.models.intent_contract import Base


class AgentProposalRecord(Base):
    __tablename__ = "agent_proposals"
    __table_args__ = (
        CheckConstraint("length(natural_language_request) BETWEEN 1 AND 4000", name="ck_agent_proposal_request_length"),
        CheckConstraint("proposed_amount IS NULL OR proposed_amount > 0", name="ck_agent_proposal_positive_amount"),
        CheckConstraint("proposed_currency IS NULL OR proposed_currency ~ '^[A-Z]{3}$'", name="ck_agent_proposal_currency"),
        CheckConstraint("status IN ('DRAFT','NEEDS_INFORMATION','READY_FOR_REVIEW','REJECTED','CONFIRMED')", name="ck_agent_proposal_status"),
        CheckConstraint("policy_decision IS NULL OR policy_decision IN ('ALLOW','DENY','NEEDS_INFORMATION')", name="ck_agent_proposal_decision"),
        CheckConstraint("provider_mode IN ('SIMULATED','LLM','OLLAMA','OPENAI')", name="ck_agent_proposal_provider_mode"),
        CheckConstraint("version > 0", name="ck_agent_proposal_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    natural_language_request: Mapped[str] = mapped_column(String(4000), nullable=False)
    requested_purpose: Mapped[str | None] = mapped_column(String(500))
    merchant_id: Mapped[str | None] = mapped_column(String(128))
    proposed_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    proposed_currency: Mapped[str | None] = mapped_column(String(3))
    contract_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("intent_contracts.id", ondelete="RESTRICT"))
    contract_version: Mapped[int | None] = mapped_column(Integer)
    explanation: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    missing_information: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    policy_decision: Mapped[str | None] = mapped_column(String(24))
    policy_reason: Mapped[str | None] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="DRAFT")
    provider_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class AgentProposalEventRecord(Base):
    __tablename__ = "agent_proposal_events"
    __table_args__ = (
        CheckConstraint("length(event_type) BETWEEN 1 AND 64", name="ck_agent_proposal_event_type_length"),
        UniqueConstraint("correlation_id", name="uq_agent_proposal_event_correlation"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    proposal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_proposals.id", ondelete="RESTRICT"), nullable=False, index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    correlation_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    event_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
