from dataclasses import dataclass


class PaymentReconciliationError(Exception):
    pass


@dataclass(frozen=True)
class ReconciliationDecision:
    action: str
    reason: str
    provider_order_id: str | None


def plan_order_reconciliation(
    *,
    attempt_status: str,
    reservation_status: str,
    provider_order_id: str | None,
) -> ReconciliationDecision:
    """
    Pure policy only.

    Does not contact PayPal, change database records,
    create orders, or capture payments.
    """
    if attempt_status not in {"PENDING", "UNKNOWN"}:
        raise PaymentReconciliationError(
            "Payment attempt is not eligible for reconciliation."
        )

    expected_reservation_status = {
        "PENDING": "EXECUTION_PENDING",
        "UNKNOWN": "OUTCOME_UNKNOWN",
    }[attempt_status]

    if reservation_status != expected_reservation_status:
        raise PaymentReconciliationError(
            "Payment attempt and reservation states disagree."
        )

    if provider_order_id is None:
        return ReconciliationDecision(
            action="HOLD_FOR_REVIEW",
            reason=(
                "Provider order ID is unknown. Preserve the "
                "reservation and do not create another order."
            ),
            provider_order_id=None,
        )

    if (
        not isinstance(provider_order_id, str)
        or not provider_order_id.strip()
        or provider_order_id != provider_order_id.strip()
        or len(provider_order_id) > 128
    ):
        raise PaymentReconciliationError(
            "Invalid provider order ID."
        )

    return ReconciliationDecision(
        action="LOOKUP_EXISTING_ORDER",
        reason=(
            "Retrieve the existing order and verify its "
            "identity, merchant, amount, and currency."
        ),
        provider_order_id=provider_order_id,
    )
