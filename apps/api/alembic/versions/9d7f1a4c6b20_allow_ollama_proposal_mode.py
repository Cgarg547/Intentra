"""Allow proposal records to identify the local Ollama provider.

Revision ID: 9d7f1a4c6b20
Revises: 8c4e21a6d9f0
"""

from alembic import op

revision = "9d7f1a4c6b20"
down_revision = "8c4e21a6d9f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_agent_proposal_provider_mode", "agent_proposals", type_="check")
    op.create_check_constraint(
        "ck_agent_proposal_provider_mode",
        "agent_proposals",
        "provider_mode IN ('SIMULATED','LLM','OLLAMA')",
    )


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM agent_proposals WHERE provider_mode = 'OLLAMA') THEN
            RAISE EXCEPTION 'Cannot downgrade while Ollama-generated proposal history exists';
        END IF;
    END $$""")
    op.drop_constraint("ck_agent_proposal_provider_mode", "agent_proposals", type_="check")
    op.create_check_constraint(
        "ck_agent_proposal_provider_mode",
        "agent_proposals",
        "provider_mode IN ('SIMULATED','LLM')",
    )
