import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint, CheckConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from intentra.models.intent_contract import Base


class AgentPaymentHandoffRecord(Base):
    """Durable one-to-one link from an owner-confirmed proposal to payment state."""

    __tablename__ = "agent_payment_handoffs"
    __table_args__ = (
        UniqueConstraint("proposal_id", name="uq_agent_handoff_proposal"),
        UniqueConstraint("reservation_id", name="uq_agent_handoff_reservation"),
        UniqueConstraint("attempt_id", name="uq_agent_handoff_attempt"),
        CheckConstraint("contract_version > 0", name="ck_agent_handoff_contract_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_proposals.id", ondelete="RESTRICT"), nullable=False
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("intent_contracts.id", ondelete="RESTRICT"), nullable=False
    )
    contract_version: Mapped[int] = mapped_column(Integer, nullable=False)
    reservation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payment_reservations.id", ondelete="RESTRICT"), nullable=False
    )
    attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payment_attempts.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
