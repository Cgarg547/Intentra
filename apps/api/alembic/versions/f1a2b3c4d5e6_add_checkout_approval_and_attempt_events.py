"""Add durable checkout approval, capture identity, and attempt events.

Revision ID: f1a2b3c4d5e6
Revises: e4b8c12d7a90
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f1a2b3c4d5e6"
down_revision = "e4b8c12d7a90"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payment_attempts", sa.Column("capture_id", sa.String(128)))
    op.add_column("payment_attempts", sa.Column("capture_idempotency_key", sa.String(108)))
    op.add_column("payment_attempts", sa.Column("capture_claimed_at", sa.DateTime(timezone=True)))
    op.create_unique_constraint("uq_payment_attempt_capture_id", "payment_attempts", ["capture_id"])
    op.create_unique_constraint("uq_payment_attempt_capture_key", "payment_attempts", ["capture_idempotency_key"])
    op.create_check_constraint("ck_payment_attempt_capture_key_length", "payment_attempts", "capture_idempotency_key IS NULL OR length(capture_idempotency_key) BETWEEN 1 AND 108")
    op.create_check_constraint("ck_payment_attempt_capture_claimed", "payment_attempts", "capture_id IS NULL OR capture_claimed_at IS NOT NULL")

    op.create_table(
        "payment_checkout_approvals",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("attempt_id", sa.Uuid(), sa.ForeignKey("payment_attempts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("provider_order_id", sa.String(128), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("verified_provider_status", sa.String(32)),
        sa.Column("verified_merchant_id", sa.String(128)),
        sa.Column("verified_amount", sa.Numeric(18, 2)),
        sa.Column("verified_currency", sa.String(3)),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("return_state_hash", sa.String(64), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("audit_correlation_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("attempt_id", name="uq_checkout_approval_attempt"),
        sa.UniqueConstraint("provider_order_id", name="uq_checkout_approval_order"),
        sa.UniqueConstraint("return_state_hash", name="uq_checkout_approval_state_hash"),
        sa.UniqueConstraint("audit_correlation_id", name="uq_checkout_approval_audit_correlation"),
        sa.CheckConstraint("state IN ('PENDING', 'APPROVED', 'CANCELLED', 'EXPIRED', 'REJECTED')", name="ck_checkout_approval_state"),
        sa.CheckConstraint("verified_amount IS NULL OR verified_amount > 0", name="ck_checkout_approval_amount_positive"),
        sa.CheckConstraint("(state = 'APPROVED' AND verified_provider_status = 'APPROVED' AND verified_merchant_id IS NOT NULL AND verified_amount IS NOT NULL AND verified_currency IS NOT NULL AND verified_at IS NOT NULL) OR (state != 'APPROVED' AND verified_provider_status IS NULL AND verified_merchant_id IS NULL AND verified_amount IS NULL AND verified_currency IS NULL AND verified_at IS NULL)", name="ck_checkout_approval_verified_fields"),
        sa.CheckConstraint("expires_at > created_at", name="ck_checkout_approval_expiry"),
    )
    op.create_index("ix_checkout_approval_state_expiry", "payment_checkout_approvals", ["state", "expires_at"])

    op.create_table(
        "payment_attempt_events",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("attempt_id", sa.Uuid(), sa.ForeignKey("payment_attempts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("event_correlation_id", sa.Uuid(), nullable=False),
        sa.Column("event_data", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("event_correlation_id", name="uq_payment_attempt_event_correlation"),
    )
    op.create_index("ix_payment_attempt_events_attempt_id", "payment_attempt_events", ["attempt_id"])
    op.execute("""CREATE FUNCTION reject_payment_attempt_event_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Payment attempt events are append-only' USING ERRCODE = '23514'; END; $$""")
    op.execute("""CREATE TRIGGER trg_payment_attempt_events_append_only BEFORE UPDATE OR DELETE ON payment_attempt_events FOR EACH ROW EXECUTE FUNCTION reject_payment_attempt_event_mutation()""")


def downgrade() -> None:
    op.execute("""DO $$ BEGIN IF EXISTS (SELECT 1 FROM payment_attempts WHERE capture_id IS NOT NULL OR capture_claimed_at IS NOT NULL) THEN RAISE EXCEPTION 'Cannot downgrade: capture evidence exists'; END IF; END $$""")
    op.execute("""DO $$ BEGIN IF EXISTS (SELECT 1 FROM payment_checkout_approvals WHERE state = 'APPROVED' OR consumed_at IS NOT NULL) THEN RAISE EXCEPTION 'Cannot downgrade: approved or consumed checkout evidence exists'; END IF; END $$""")
    op.execute("DROP TRIGGER trg_payment_attempt_events_append_only ON payment_attempt_events")
    op.execute("DROP FUNCTION reject_payment_attempt_event_mutation()")
    op.drop_index("ix_payment_attempt_events_attempt_id", table_name="payment_attempt_events")
    op.drop_table("payment_attempt_events")
    op.drop_index("ix_checkout_approval_state_expiry", table_name="payment_checkout_approvals")
    op.drop_table("payment_checkout_approvals")
    op.drop_constraint("ck_payment_attempt_capture_claimed", "payment_attempts", type_="check")
    op.drop_constraint("ck_payment_attempt_capture_key_length", "payment_attempts", type_="check")
    op.drop_constraint("uq_payment_attempt_capture_key", "payment_attempts", type_="unique")
    op.drop_constraint("uq_payment_attempt_capture_id", "payment_attempts", type_="unique")
    op.drop_column("payment_attempts", "capture_claimed_at")
    op.drop_column("payment_attempts", "capture_idempotency_key")
    op.drop_column("payment_attempts", "capture_id")
