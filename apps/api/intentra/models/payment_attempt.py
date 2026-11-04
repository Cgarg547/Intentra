import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Numeric,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from intentra.models.intent_contract import Base


class PaymentAttemptRecord(Base):
    __tablename__ = "payment_attempts"

    __table_args__ = (
        UniqueConstraint(
            "reservation_id",
            name="uq_payment_attempt_reservation",
        ),
        UniqueConstraint(
            "provider_idempotency_key",
            name="uq_payment_attempt_provider_key",
        ),
        UniqueConstraint(
            "provider_order_id",
            name="uq_payment_attempt_provider_order",
        ),
        UniqueConstraint("capture_id", name="uq_payment_attempt_capture_id"),
        UniqueConstraint("capture_idempotency_key", name="uq_payment_attempt_capture_key"),
        CheckConstraint("capture_idempotency_key IS NULL OR length(capture_idempotency_key) BETWEEN 1 AND 108", name="ck_payment_attempt_capture_key_length"),
        CheckConstraint("capture_id IS NULL OR capture_claimed_at IS NOT NULL", name="ck_payment_attempt_capture_claimed"),
        CheckConstraint(
            "status IN ('PENDING', 'SUCCEEDED', 'FAILED', 'UNKNOWN')",
            name="ck_payment_attempt_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    reservation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payment_reservations.id"),
        nullable=False,
        index=True,
    )

    provider_idempotency_key: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    provider_order_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    capture_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    capture_idempotency_key: Mapped[str | None] = mapped_column(String(108), nullable=True)
    capture_claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
