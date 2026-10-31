"""Add durable payment reconciliation evidence.

Revision ID: d8f3a91b6c20
Revises: c7a42f91e805
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "d8f3a91b6c20"
down_revision = "c7a42f91e805"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payment_reconciliation_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("provider_order_id", sa.String(128)),
        sa.Column("provider_status", sa.String(32)),
        sa.Column(
            "evidence_data",
            postgresql.JSONB(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["payment_attempts.id"],
        ),
        sa.UniqueConstraint(
            "operation_id",
            name="uq_payment_reconciliation_operation",
        ),
        sa.CheckConstraint(
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

    op.create_index(
        "ix_payment_reconciliation_events_attempt_id",
        "payment_reconciliation_events",
        ["attempt_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_payment_reconciliation_events_attempt_id",
        table_name="payment_reconciliation_events",
    )
    op.drop_table("payment_reconciliation_events")
