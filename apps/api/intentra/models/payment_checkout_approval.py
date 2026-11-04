import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from intentra.models.intent_contract import Base


class PaymentCheckoutApprovalRecord(Base):
    __tablename__ = "payment_checkout_approvals"
    __table_args__ = (
        CheckConstraint("state IN ('PENDING', 'APPROVED', 'CANCELLED', 'EXPIRED', 'REJECTED')", name="ck_checkout_approval_state"),
        CheckConstraint("verified_amount IS NULL OR verified_amount > 0", name="ck_checkout_approval_amount_positive"),
        CheckConstraint(
            "(state = 'APPROVED' AND verified_provider_status = 'APPROVED' AND verified_merchant_id IS NOT NULL AND verified_amount IS NOT NULL AND verified_currency IS NOT NULL AND verified_at IS NOT NULL) OR "
            "(state != 'APPROVED' AND verified_provider_status IS NULL AND verified_merchant_id IS NULL AND verified_amount IS NULL AND verified_currency IS NULL AND verified_at IS NULL)",
            name="ck_checkout_approval_verified_fields",
        ),
        CheckConstraint("expires_at > created_at", name="ck_checkout_approval_expiry"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payment_attempts.id", ondelete="RESTRICT"), nullable=False, unique=True)
    provider_order_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    verified_provider_status: Mapped[str | None] = mapped_column(String(32))
    verified_merchant_id: Mapped[str | None] = mapped_column(String(128))
    verified_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    verified_currency: Mapped[str | None] = mapped_column(String(3))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    return_state_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    audit_correlation_id: Mapped[uuid.UUID] = mapped_column(nullable=False, default=uuid.uuid4, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
