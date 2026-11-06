import pytest

from intentra.schema_head import CURRENT_ALEMBIC_HEAD, has_current_schema_head


def test_current_single_schema_head_is_accepted():
    assert has_current_schema_head([CURRENT_ALEMBIC_HEAD])


@pytest.mark.parametrize("revisions", [
    [],
    ["f1a2b3c4d5e6"],  # stale applied revision
    ["future-unrecognized-revision"],
    [CURRENT_ALEMBIC_HEAD, "future-unrecognized-revision"],  # branched state
    ["f1a2b3c4d5e6", CURRENT_ALEMBIC_HEAD],  # branched/stale state
])
def test_non_current_or_branched_schema_revisions_are_rejected(revisions):
    assert not has_current_schema_head(revisions)
