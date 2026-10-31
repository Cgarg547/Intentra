"""Add durable payment attempts.

Revision ID: b6e91c2a740d
Revises: 9c2d7e61b4a0
"""

from alembic import op
import sqlalchemy as sa

revision = "b6e91c2a740d"
down_revision = "9c2d7e61b4a0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payment_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("reservation_id", sa.Uuid(), nullable=False),
        sa.Column(
            "provider_idempotency_key",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "provider_order_id",
            sa.String(length=128),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["reservation_id"],
            ["payment_reservations.id"],
        ),
        sa.UniqueConstraint(
            "reservation_id",
            name="uq_payment_attempt_reservation",
        ),
        sa.UniqueConstraint(
            "provider_idempotency_key",
            name="uq_payment_attempt_provider_key",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'SUCCEEDED', 'FAILED', 'UNKNOWN')",
            name="ck_payment_attempt_status",
        ),
    )

    op.create_index(
        "ix_payment_attempts_reservation_id",
        "payment_attempts",
        ["reservation_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_payment_attempts_reservation_id",
        table_name="payment_attempts",
    )
    op.drop_table("payment_attempts")
