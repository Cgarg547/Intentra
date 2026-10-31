"""Enforce unique PayPal provider order IDs.

Revision ID: c7a42f91e805
Revises: b6e91c2a740d
"""

from alembic import op
import sqlalchemy as sa


revision = "c7a42f91e805"
down_revision = "b6e91c2a740d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_payment_attempt_provider_order",
        "payment_attempts",
        ["provider_order_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_payment_attempt_provider_order",
        "payment_attempts",
        type_="unique",
    )
