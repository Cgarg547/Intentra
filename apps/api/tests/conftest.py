import pytest



DATABASE_INTEGRATION_MODULES = frozenset({
    "test_agent_payment_handoff.py",
    "test_agent_proposals.py",
    "test_checkout_approval.py",
    "test_contract_integration.py",
    "test_payment_attempts.py",
    "test_payment_capture.py",
    "test_payment_capture_api.py",
    "test_payment_capture_reconciliation.py",
    "test_payment_checkout_diagnostics.py",
    "test_payment_execution.py",
    "test_payment_frontend_api.py",
    "test_payment_integration.py",
    "test_payment_order_binding.py",
    "test_payment_order_recovery.py",
    "test_payment_outcomes.py",
    "test_payment_reconciliation_evidence.py",
    "test_payment_reconciliation_finalize.py",
    "test_payment_reconciliation_runner.py",
    "test_workspace_api.py",
})


def pytest_collection_modifyitems(items):
    """Label known DB-writing modules for selective CI execution.

    Every listed module imports ``test_contract_integration`` before importing
    application database code, so target validation happens before this hook.
    The hook supplies selection metadata only; it is not the safety boundary.
    """
    for item in items:
        if item.path.name in DATABASE_INTEGRATION_MODULES:
            item.add_marker(pytest.mark.database_integration)
