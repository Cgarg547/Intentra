"""Add owner-scoped AI purchase proposals and append-only audit events.

Revision ID: 7a91d4c3e2b0
Revises: f1a2b3c4d5e6
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "7a91d4c3e2b0"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_proposals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("natural_language_request", sa.String(length=4000), nullable=False),
        sa.Column("requested_purpose", sa.String(length=500)),
        sa.Column("merchant_id", sa.String(length=128)),
        sa.Column("proposed_amount", sa.Numeric(18, 2)),
        sa.Column("proposed_currency", sa.String(length=3)),
        sa.Column("contract_id", sa.Uuid(), sa.ForeignKey("intent_contracts.id", ondelete="RESTRICT")),
        sa.Column("contract_version", sa.Integer()),
        sa.Column("explanation", sa.String(length=1000), nullable=False),
        sa.Column("missing_information", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("policy_decision", sa.String(length=24)),
        sa.Column("policy_reason", sa.String(length=512)),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("provider_mode", sa.String(length=16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("length(natural_language_request) BETWEEN 1 AND 4000", name="ck_agent_proposal_request_length"),
        sa.CheckConstraint("proposed_amount IS NULL OR proposed_amount > 0", name="ck_agent_proposal_positive_amount"),
        sa.CheckConstraint("proposed_currency IS NULL OR proposed_currency ~ '^[A-Z]{3}$'", name="ck_agent_proposal_currency"),
        sa.CheckConstraint("status IN ('DRAFT','NEEDS_INFORMATION','READY_FOR_REVIEW','REJECTED','CONFIRMED')", name="ck_agent_proposal_status"),
        sa.CheckConstraint("policy_decision IS NULL OR policy_decision IN ('ALLOW','DENY','NEEDS_INFORMATION')", name="ck_agent_proposal_decision"),
        sa.CheckConstraint("provider_mode IN ('SIMULATED','LLM')", name="ck_agent_proposal_provider_mode"),
        sa.CheckConstraint("version > 0", name="ck_agent_proposal_version"),
    )
    op.create_index("ix_agent_proposals_owner_id", "agent_proposals", ["owner_id"])
    op.create_index("ix_agent_proposals_owner_created", "agent_proposals", ["owner_id", "created_at"])
    op.create_table(
        "agent_proposal_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("proposal_id", sa.Uuid(), sa.ForeignKey("agent_proposals.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("correlation_id", sa.Uuid(), nullable=False),
        sa.Column("event_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("correlation_id", name="uq_agent_proposal_event_correlation"),
        sa.CheckConstraint("length(event_type) BETWEEN 1 AND 64", name="ck_agent_proposal_event_type_length"),
    )
    op.create_index("ix_agent_proposal_events_proposal_id", "agent_proposal_events", ["proposal_id"])
    op.execute("""CREATE FUNCTION reject_agent_proposal_event_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Agent proposal events are append-only' USING ERRCODE = '23514'; END; $$""")
    op.execute("""CREATE TRIGGER trg_agent_proposal_events_append_only BEFORE UPDATE OR DELETE ON agent_proposal_events FOR EACH ROW EXECUTE FUNCTION reject_agent_proposal_event_mutation()""")


def downgrade() -> None:
    # Proposals and their decisions form an audit record; refuse to silently erase it.
    op.execute("""DO $$ BEGIN IF EXISTS (SELECT 1 FROM agent_proposals WHERE status = 'CONFIRMED') OR EXISTS (SELECT 1 FROM agent_proposal_events) THEN RAISE EXCEPTION 'Cannot downgrade: agent proposal audit evidence exists'; END IF; END $$""")
    op.execute("DROP TRIGGER trg_agent_proposal_events_append_only ON agent_proposal_events")
    op.execute("DROP FUNCTION reject_agent_proposal_event_mutation()")
    op.drop_index("ix_agent_proposal_events_proposal_id", table_name="agent_proposal_events")
    op.drop_table("agent_proposal_events")
    op.drop_index("ix_agent_proposals_owner_created", table_name="agent_proposals")
    op.drop_index("ix_agent_proposals_owner_id", table_name="agent_proposals")
    op.drop_table("agent_proposals")
