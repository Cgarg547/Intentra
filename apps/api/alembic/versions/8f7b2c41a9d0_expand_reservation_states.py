"""Expand reservation states for payment execution lifecycle.

Revision ID: 8f7b2c41a9d0
Revises: 5a644cf96eec
"""

from alembic import op

revision = "8f7b2c41a9d0"
down_revision = "5a644cf96eec"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_reservation_status",
        "payment_reservations",
        type_="check",
    )

    op.create_check_constraint(
        "ck_reservation_status",
        "payment_reservations",
        "status IN ("
        "'RESERVED', "
        "'EXECUTION_PENDING', "
        "'OUTCOME_UNKNOWN', "
        "'CAPTURED', "
        "'CANCELLED', "
        "'BLOCKED'"
        ")",
    )


def downgrade() -> None:
    op.execute(
        "DO $$ BEGIN "
        "IF EXISTS ("
        "SELECT 1 FROM payment_reservations "
        "WHERE status NOT IN ('RESERVED', 'BLOCKED')"
        ") THEN "
        "RAISE EXCEPTION 'Cannot downgrade: execution states exist'; "
        "END IF; "
        "END $$;"
    )

    op.drop_constraint(
        "ck_reservation_status",
        "payment_reservations",
        type_="check",
    )

    op.create_check_constraint(
        "ck_reservation_status",
        "payment_reservations",
        "status IN ('RESERVED', 'BLOCKED')",
    )
