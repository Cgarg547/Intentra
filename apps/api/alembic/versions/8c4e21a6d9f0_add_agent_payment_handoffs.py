"""Persist one-time proposal-to-payment preparation links.

Revision ID: 8c4e21a6d9f0
Revises: 7a91d4c3e2b0
"""

from alembic import op
import sqlalchemy as sa

revision = "8c4e21a6d9f0"
down_revision = "7a91d4c3e2b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_payment_handoffs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("proposal_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("contract_id", sa.Uuid(), nullable=False),
        sa.Column("contract_version", sa.Integer(), nullable=False),
        sa.Column("reservation_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("contract_version > 0", name="ck_agent_handoff_contract_version"),
        sa.ForeignKeyConstraint(["attempt_id"], ["payment_attempts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["contract_id"], ["intent_contracts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["proposal_id"], ["agent_proposals.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reservation_id"], ["payment_reservations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("proposal_id", name="uq_agent_handoff_proposal"),
        sa.UniqueConstraint("reservation_id", name="uq_agent_handoff_reservation"),
        sa.UniqueConstraint("attempt_id", name="uq_agent_handoff_attempt"),
    )
    op.create_index("ix_agent_payment_handoffs_owner_id", "agent_payment_handoffs", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_payment_handoffs_owner_id", table_name="agent_payment_handoffs")
    op.drop_table("agent_payment_handoffs")
