"""Run the reviewed offline audit subset; never connect to a service or database.

From apps/api: .venv/bin/python scripts/offline_checks.py
Use --list to inspect the selected files without running them.
Database-writing integration suites are deliberately excluded.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import socket
import sys

API_ROOT = Path(__file__).resolve().parents[1]
TESTS = (
    "tests/test_agent_provider.py",
    "tests/test_agent_labeled_purchase.py",
    "tests/test_agent_failure_offline.py",
    "tests/test_integration_db_guard.py",
    "tests/test_auth_security.py",
    "tests/test_authorization.py",
    "tests/test_merchant_registry.py",
    "tests/test_payment_reconciliation.py",
    "tests/test_paypal_sandbox.py",
    "tests/test_paypal_sandbox_local.py",
    "tests/test_recover_known_paypal_order.py",
)


def _deny_network(*_args, **_kwargs):
    raise RuntimeError("Network access is prohibited by the offline check runner")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="List the reviewed subset only")
    args = parser.parse_args()
    if args.list:
        print("\n".join(TESTS))
        return 0

    os.chdir(API_ROOT)
    sys.path.insert(0, str(API_ROOT))
    # Affect this process only, never the already-running backend configuration.
    os.environ["DATABASE_URL"] = "postgresql+asyncpg://offline:offline@127.0.0.1:1/offline"
    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    socket.socket.connect = _deny_network
    socket.socket.connect_ex = _deny_network
    socket.socket.sendto = _deny_network
    socket.create_connection = _deny_network
    socket.getaddrinfo = _deny_network

    import pytest

    return pytest.main(["-p", "pytest_asyncio.plugin", "-q", *TESTS])


if __name__ == "__main__":
    raise SystemExit(main())
