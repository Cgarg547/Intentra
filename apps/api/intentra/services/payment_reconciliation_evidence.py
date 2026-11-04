import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from intentra.models.payment_reconciliation_event import (
    PaymentReconciliationEventRecord,
)


class ReconciliationEvidenceError(Exception):
    pass


ALLOWED_EVENTS = frozenset({
    "HOLD_FOR_REVIEW",
    "ORDER_VERIFIED",
    "LOOKUP_FAILED",
    "VERIFICATION_REJECTED",
    "STALE_RESULT",
})

ALLOWED_EVIDENCE_KEYS = frozenset({
    "reason_code",
    "capture_id",
    "verified_merchant_id",
    "verified_amount",
    "verified_currency",
})


@dataclass(frozen=True)
class EvidenceResult:
    event_id: uuid.UUID
    operation_id: uuid.UUID
    attempt_id: uuid.UUID
    event_type: str
    created: bool


async def record_reconciliation_evidence(
    db: AsyncSession,
    *,
    operation_id: uuid.UUID,
    attempt_id: uuid.UUID,
    event_type: str,
    provider_order_id: str | None = None,
    provider_status: str | None = None,
    evidence_data: dict | None = None,
) -> EvidenceResult:
    """Persist a sanitized reconciliation observation.

    The caller owns the transaction. This function does not commit,
    change payment state, or communicate with PayPal.
    """
    if not isinstance(operation_id, uuid.UUID):
        raise ReconciliationEvidenceError("Invalid operation ID.")

    if not isinstance(attempt_id, uuid.UUID):
        raise ReconciliationEvidenceError("Invalid attempt ID.")

    if event_type not in ALLOWED_EVENTS:
        raise ReconciliationEvidenceError("Unsupported evidence event.")

    for value, maximum, label in (
        (provider_order_id, 128, "provider order ID"),
        (provider_status, 32, "provider status"),
    ):
        if value is not None and (
            not isinstance(value, str)
            or not value
            or value != value.strip()
            or len(value) > maximum
        ):
            raise ReconciliationEvidenceError(f"Invalid {label}.")

    data = {} if evidence_data is None else evidence_data

    if not isinstance(data, dict):
        raise ReconciliationEvidenceError("Invalid evidence data.")

    if not all(
        isinstance(key, str) and key in ALLOWED_EVIDENCE_KEYS
        for key in data
    ):
        raise ReconciliationEvidenceError(
            "Evidence contains unsupported fields."
        )

    if not all(
        isinstance(value, str)
        and 0 < len(value) <= 128
        and value == value.strip()
        for value in data.values()
    ):
        raise ReconciliationEvidenceError(
            "Evidence values must be bounded strings."
        )

    # INSERT ... ON CONFLICT is atomic in PostgreSQL.
    # Concurrent calls using the same operation ID cannot
    # create duplicate evidence rows.
    statement = (
        insert(PaymentReconciliationEventRecord)
        .values(
            id=uuid.uuid4(),
            operation_id=operation_id,
            attempt_id=attempt_id,
            event_type=event_type,
            provider_order_id=provider_order_id,
            provider_status=provider_status,
            evidence_data=dict(data),
        )
        .on_conflict_do_nothing(
            constraint="uq_payment_reconciliation_operation"
        )
        .returning(PaymentReconciliationEventRecord.id)
    )

    inserted_id = await db.scalar(statement)

    existing = await db.scalar(
        select(PaymentReconciliationEventRecord).where(
            PaymentReconciliationEventRecord.operation_id == operation_id
        )
    )

    if existing is None:
        raise ReconciliationEvidenceError(
            "Unable to retrieve reconciliation evidence."
        )

    if (
        existing.attempt_id != attempt_id
        or existing.event_type != event_type
        or existing.provider_order_id != provider_order_id
        or existing.provider_status != provider_status
        or existing.evidence_data != data
    ):
        raise ReconciliationEvidenceError(
            "Conflicting reconciliation evidence for operation ID."
        )

    return EvidenceResult(
        event_id=existing.id,
        operation_id=existing.operation_id,
        attempt_id=existing.attempt_id,
        event_type=existing.event_type,
        created=inserted_id is not None,
    )
