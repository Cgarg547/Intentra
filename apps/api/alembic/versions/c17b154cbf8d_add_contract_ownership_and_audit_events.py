"""Add contract ownership and audit events.

Revision ID: c17b154cbf8d
Revises: cff869226bbc
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c17b154cbf8d"
down_revision: Union[str, Sequence[str], None] = "cff869226bbc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    op.add_column(
        "intent_contracts",
        sa.Column("owner_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "intent_contracts",
        sa.Column(
            "version",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
    )
    op.add_column(
        "intent_contracts",
        sa.Column("approved_by", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "intent_contracts",
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.create_foreign_key(
        "fk_intent_contracts_owner_id_users",
        "intent_contracts",
        "users",
        ["owner_id"],
        ["id"],
    )

    op.create_foreign_key(
        "fk_intent_contracts_approved_by_users",
        "intent_contracts",
        "users",
        ["approved_by"],
        ["id"],
    )

    op.create_check_constraint(
        "ck_intent_positive_version",
        "intent_contracts",
        "version > 0",
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("contract_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("contract_version", sa.Integer(), nullable=False),
        sa.Column(
            "event_data",
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
            ["contract_id"],
            ["intent_contracts.id"],
            name="fk_audit_events_contract_id",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name="fk_audit_events_actor_id",
        ),
    )


def downgrade() -> None:
    op.drop_table("audit_events")

    op.drop_constraint(
        "ck_intent_positive_version",
        "intent_contracts",
        type_="check",
    )

    op.drop_constraint(
        "fk_intent_contracts_approved_by_users",
        "intent_contracts",
        type_="foreignkey",
    )

    op.drop_constraint(
        "fk_intent_contracts_owner_id_users",
        "intent_contracts",
        type_="foreignkey",
    )

    op.drop_column("intent_contracts", "revoked_at")
    op.drop_column("intent_contracts", "approved_by")
    op.drop_column("intent_contracts", "version")
    op.drop_column("intent_contracts", "owner_id")

    op.drop_table("users")
