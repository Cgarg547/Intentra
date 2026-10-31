import pytest

from intentra.services.payment_reconciliation import (
    PaymentReconciliationError,
    plan_order_reconciliation,
)


@pytest.mark.parametrize(
    "attempt_status,reservation_status",
    [
        ("PENDING", "EXECUTION_PENDING"),
        ("UNKNOWN", "OUTCOME_UNKNOWN"),
    ],
)
def test_unknown_order_id_preserves_uncertainty(
    attempt_status,
    reservation_status,
):
    decision = plan_order_reconciliation(
        attempt_status=attempt_status,
        reservation_status=reservation_status,
        provider_order_id=None,
    )

    assert decision.action == "HOLD_FOR_REVIEW"
    assert decision.provider_order_id is None


@pytest.mark.parametrize(
    "attempt_status,reservation_status",
    [
        ("PENDING", "EXECUTION_PENDING"),
        ("UNKNOWN", "OUTCOME_UNKNOWN"),
    ],
)
def test_known_order_id_requires_lookup(
    attempt_status,
    reservation_status,
):
    decision = plan_order_reconciliation(
        attempt_status=attempt_status,
        reservation_status=reservation_status,
        provider_order_id="MOCK-ORDER-123",
    )

    assert decision.action == "LOOKUP_EXISTING_ORDER"
    assert decision.provider_order_id == "MOCK-ORDER-123"


@pytest.mark.parametrize(
    "attempt_status,reservation_status",
    [
        ("SUCCEEDED", "CAPTURED"),
        ("FAILED", "CANCELLED"),
        ("PENDING", "OUTCOME_UNKNOWN"),
        ("UNKNOWN", "EXECUTION_PENDING"),
    ],
)
def test_terminal_or_inconsistent_states_rejected(
    attempt_status,
    reservation_status,
):
    with pytest.raises(PaymentReconciliationError):
        plan_order_reconciliation(
            attempt_status=attempt_status,
            reservation_status=reservation_status,
            provider_order_id="MOCK-ORDER-123",
        )


@pytest.mark.parametrize(
    "order_id",
    ["", " ", " MOCK-ORDER", "MOCK-ORDER ", "X" * 129],
)
def test_invalid_order_ids_rejected(order_id):
    with pytest.raises(PaymentReconciliationError):
        plan_order_reconciliation(
            attempt_status="PENDING",
            reservation_status="EXECUTION_PENDING",
            provider_order_id=order_id,
        )
