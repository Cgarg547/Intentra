"""Shared fail-closed compatibility check for local operational scripts."""

from collections.abc import Iterable


# Keep this value synchronized with the repository's sole Alembic head.  The
# focused graph test prevents a new migration from silently making local
# recovery/setup scripts accept an obsolete schema.
CURRENT_ALEMBIC_HEAD = "9d7f1a4c6b20"


def has_current_schema_head(revisions: Iterable[object]) -> bool:
    """Return true only for exactly one applied, current Alembic revision.

    Multiple rows in ``alembic_version`` indicate a branched/ambiguous state
    and must be rejected by the payment-recovery and Sandbox setup tools.
    """
    return tuple(revisions) == (CURRENT_ALEMBIC_HEAD,)
