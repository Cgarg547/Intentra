import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from intentra.models.intent_contract import Base


class PaymentReservationRecord(Base):
    __tablename__ = "payment_reservations"

    __table_args__ = (
        UniqueConstraint(
            "contract_id",
            "idempotency_key",
            name="uq_reservation_contract_idempotency",
        ),
        CheckConstraint(
            "amount > 0",
            name="ck_reservation_positive_amount",
        ),
        CheckConstraint(
            "contract_version > 0",
            name="ck_reservation_positive_version",
        ),
        CheckConstraint(
            (
                "status IN ("
                "'RESERVED', "
                "'EXECUTION_PENDING', "
                "'OUTCOME_UNKNOWN', "
                "'CAPTURED', "
                "'CANCELLED', "
                "'BLOCKED'"
                ")"
            ),
            name="ck_reservation_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    contract_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("intent_contracts.id"),
        nullable=False,
        index=True,
    )

    actor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )

    contract_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    merchant_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    reason: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
