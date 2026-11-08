"""Allow proposal records to identify OpenAI-compatible hosted providers.

Revision ID: a3d8e1f4b7c2
Revises: 9d7f1a4c6b20
"""

from alembic import op


revision = "a3d8e1f4b7c2"
down_revision = "9d7f1a4c6b20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_agent_proposal_provider_mode", "agent_proposals", type_="check")
    op.create_check_constraint(
        "ck_agent_proposal_provider_mode",
        "agent_proposals",
        "provider_mode IN ('SIMULATED','LLM','OLLAMA','OPENAI')",
    )


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM agent_proposals WHERE provider_mode = 'OPENAI') THEN
            RAISE EXCEPTION 'Cannot downgrade while OpenAI-compatible proposal history exists';
        END IF;
    END $$""")
    op.drop_constraint("ck_agent_proposal_provider_mode", "agent_proposals", type_="check")
    op.create_check_constraint(
        "ck_agent_proposal_provider_mode",
        "agent_proposals",
        "provider_mode IN ('SIMULATED','LLM','OLLAMA')",
    )
