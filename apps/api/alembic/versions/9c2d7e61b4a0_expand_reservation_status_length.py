"""Expand payment reservation status column length.

Revision ID: 9c2d7e61b4a0
Revises: 8f7b2c41a9d0
"""

from alembic import op
import sqlalchemy as sa

revision = "9c2d7e61b4a0"
down_revision = "8f7b2c41a9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "payment_reservations",
        "status",
        existing_type=sa.String(length=16),
        type_=sa.String(length=32),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM payment_reservations
                WHERE length(status) > 16
            ) THEN
                RAISE EXCEPTION
                    'Cannot downgrade: reservation statuses exceed 16 characters';
            END IF;
        END $$;
        """
    )

    op.alter_column(
        "payment_reservations",
        "status",
        existing_type=sa.String(length=32),
        type_=sa.String(length=16),
        existing_nullable=False,
    )
