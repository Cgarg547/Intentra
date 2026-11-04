from alembic.config import Config
from alembic.script import ScriptDirectory

from scripts.paypal_sandbox_local import TARGET_REVISION


def test_local_launcher_revision_matches_the_single_alembic_head():
    migration_graph = ScriptDirectory.from_config(Config("alembic.ini"))
    assert migration_graph.get_heads() == [TARGET_REVISION]
