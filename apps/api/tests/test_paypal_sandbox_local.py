from alembic.config import Config
from alembic.script import ScriptDirectory

from intentra.schema_head import CURRENT_ALEMBIC_HEAD
from scripts import recover_known_paypal_order as recovery
from scripts.paypal_sandbox_local import TARGET_REVISION


def test_local_launcher_revision_matches_the_single_alembic_head():
    migration_graph = ScriptDirectory.from_config(Config("alembic.ini"))
    assert migration_graph.get_heads() == [TARGET_REVISION]
    assert TARGET_REVISION == CURRENT_ALEMBIC_HEAD
    assert recovery.TARGET_REVISION == CURRENT_ALEMBIC_HEAD
