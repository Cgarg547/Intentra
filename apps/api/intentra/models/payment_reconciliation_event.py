import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from intentra.models.intent_contract import Base


class PaymentReconciliationEventRecord(Base):
    __tablename__ = "payment_reconciliation_events"

    __table_args__ = (
        UniqueConstraint(
            "operation_id",
            name="uq_payment_reconciliation_operation",
        ),
        CheckConstraint(
            "event_type IN ("
            "'HOLD_FOR_REVIEW', "
            "'ORDER_VERIFIED', "
            "'LOOKUP_FAILED', "
            "'VERIFICATION_REJECTED', "
            "'STALE_RESULT'"
            ")",
            name="ck_payment_reconciliation_event_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    operation_id: Mapped[uuid.UUID] = mapped_column(
        nullable=False,
    )

    attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payment_attempts.id"),
        nullable=False,
        index=True,
    )

    event_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    provider_order_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    provider_status: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    evidence_data: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
