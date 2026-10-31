"""Prevent updates and deletes to reconciliation evidence.

Revision ID: e4b8c12d7a90
Revises: d8f3a91b6c20
"""

from alembic import op


revision = "e4b8c12d7a90"
down_revision = "d8f3a91b6c20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE FUNCTION reject_reconciliation_evidence_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION
                'Payment reconciliation evidence is append-only'
                USING ERRCODE = '23514';
        END;
        $$;
    """)

    op.execute("""
        CREATE TRIGGER trg_reconciliation_evidence_append_only
        BEFORE UPDATE OR DELETE
        ON payment_reconciliation_events
        FOR EACH ROW
        EXECUTE FUNCTION reject_reconciliation_evidence_mutation();
    """)


def downgrade() -> None:
    op.execute("""
        DROP TRIGGER trg_reconciliation_evidence_append_only
        ON payment_reconciliation_events;
    """)

    op.execute("""
        DROP FUNCTION reject_reconciliation_evidence_mutation();
    """)
