from alembic.config import Config
from alembic.script import ScriptDirectory

from intentra.schema_head import CURRENT_ALEMBIC_HEAD
from scripts import recover_known_paypal_order as recovery
from scripts import paypal_sandbox_local as sandbox_local
from scripts.paypal_sandbox_local import TARGET_REVISION


def test_local_launcher_revision_matches_the_single_alembic_head():
    migration_graph = ScriptDirectory.from_config(Config("alembic.ini"))
    assert migration_graph.get_heads() == [TARGET_REVISION]
    assert TARGET_REVISION == CURRENT_ALEMBIC_HEAD
    assert recovery.TARGET_REVISION == CURRENT_ALEMBIC_HEAD


def test_disposable_sandbox_database_requires_explicit_opt_in(monkeypatch):
    url = (
        "postgresql+asyncpg://intentra_sandbox_runner:local-password@"
        "127.0.0.1:5434/intentra_sandbox_demo"
    )
    monkeypatch.setattr(sandbox_local, "get_database_url", lambda: url)
    monkeypatch.delenv(sandbox_local.DISPOSABLE_SANDBOX_DATABASE_FLAG, raising=False)

    try:
        sandbox_local._database_url_for_development()
    except RuntimeError:
        pass
    else:
        raise AssertionError("disposable Sandbox database must require an explicit opt-in")

    monkeypatch.setenv(sandbox_local.DISPOSABLE_SANDBOX_DATABASE_FLAG, "1")
    assert sandbox_local._database_url_for_development() == url
