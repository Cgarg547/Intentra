"""Provider orchestration across durable payment state transitions."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from intentra.models.agent_payment_handoff import AgentPaymentHandoffRecord
from intentra.models.agent_proposal import AgentProposalRecord
from intentra.models.intent_contract import IntentContractRecord
from intentra.models.payment_attempt_event import PaymentAttemptEventRecord
from intentra.models.payment_attempt import PaymentAttemptRecord
from intentra.models.payment_reservation import PaymentReservationRecord
from intentra.services.merchant_registry import MerchantRegistryError, TrustedMerchantRegistry
from intentra.services.payment_execution import claim_payment_execution
from intentra.services.payment_order_binding import bind_provider_order
from intentra.services.paypal_sandbox import (
    PayPalOrderNotSubmittedError,
    PayPalOrderOutcomeUnknownError,
    PayPalOrderRejectedError,
    PayPalSandboxClient,
    PayPalSandboxError,
    validate_paypal_order,
)
from intentra.services.payment_capture import PaymentCaptureError, capture_approved_payment


AGENT_PROPOSAL_MAX_AGE = timedelta(hours=24)


class PaymentOrchestrationError(Exception):
    def __init__(self, message: str, *, code: str = "PAYMENT_NOT_ELIGIBLE", status_code: int = 409):
        self.code = code
        self.status_code = status_code
        super().__init__(message)


@dataclass(frozen=True)
class PaymentLaunch:
    attempt_id: uuid.UUID
    provider_order_id: str
    approval_url: str
    status: str


def _approval_url(order: dict) -> str:
    links = order.get("links")
    if not isinstance(links, list):
        raise PaymentOrchestrationError(
            "PayPal order has no approval link.",
            code="APPROVAL_LINK_INVALID", status_code=503,
        )
    for link in links:
        if isinstance(link, dict) and link.get("rel") in {"approve", "payer-action"}:
            href = link.get("href")
            if isinstance(href, str):
                parsed = urlsplit(href)
                if parsed.scheme == "https" and parsed.hostname == "www.sandbox.paypal.com" and parsed.username is None and parsed.password is None:
                    return href
    raise PaymentOrchestrationError(
        "PayPal order has no valid Sandbox approval link.",
        code="APPROVAL_LINK_INVALID", status_code=503,
    )


def _checkout_url(base_url: str | None, attempt_id: uuid.UUID) -> str | None:
    if base_url is None:
        return None
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}attempt_id={attempt_id}"


async def create_payment_order(
    db: AsyncSession, *, reservation_id: uuid.UUID, actor_id: uuid.UUID,
    registry: TrustedMerchantRegistry, paypal: PayPalSandboxClient,
    return_url: str | None = None, cancel_url: str | None = None,
) -> PaymentLaunch:
    claim = await claim_payment_execution(
        db, reservation_id=reservation_id, actor_id=actor_id,
    )
    if claim.status == "UNKNOWN":
        raise PaymentOrchestrationError(
            "Unknown payment outcome must be reconciled before retry.",
            code="PROVIDER_OUTCOME_UNKNOWN", status_code=409,
        )

    # claim_payment_execution commits new claims, but its existing-attempt
    # lookup leaves a SQLAlchemy autobegun read transaction open.
    await db.rollback()
    async with db.begin():
        attempt_ref = await db.get(PaymentAttemptRecord, claim.attempt_id)
        reservation_ref = await db.get(PaymentReservationRecord, reservation_id)
        if attempt_ref is None or reservation_ref is None or reservation_ref.actor_id != actor_id:
            raise PaymentOrchestrationError("Existing attempt is unavailable.")
        contract = await db.scalar(select(IntentContractRecord).where(
            IntentContractRecord.id == reservation_ref.contract_id,
            IntentContractRecord.owner_id == actor_id,
        ).with_for_update().execution_options(populate_existing=True))
        reservation = await db.scalar(select(PaymentReservationRecord).where(
            PaymentReservationRecord.id == reservation_id,
            PaymentReservationRecord.actor_id == actor_id,
        ).with_for_update().execution_options(populate_existing=True))
        attempt = await db.scalar(select(PaymentAttemptRecord).where(
            PaymentAttemptRecord.id == claim.attempt_id,
            PaymentAttemptRecord.reservation_id == reservation_id,
        ).with_for_update().execution_options(populate_existing=True))
        if attempt is None or reservation is None or contract is None:
            raise PaymentOrchestrationError("Existing attempt is unavailable.")
        if (contract.status != "APPROVED" or contract.version != reservation.contract_version
            or reservation.status != "EXECUTION_PENDING" or attempt.status != "PENDING"
            or reservation.merchant_id != contract.merchant_id
            or reservation.currency != contract.currency or reservation.amount <= 0
            or reservation.amount > contract.maximum_amount):
            raise PaymentOrchestrationError("Existing attempt is no longer authorized.")

        events = (await db.scalars(select(PaymentAttemptEventRecord).where(
            PaymentAttemptEventRecord.attempt_id == attempt.id,
        ).order_by(PaymentAttemptEventRecord.created_at, PaymentAttemptEventRecord.id))).all()
        accepted = next((event for event in reversed(events)
                         if event.event_type == "ORDER_CREATE_PROVIDER_ACCEPTED"), None)
        order_id = attempt.provider_order_id
        recovery_order_id = None
        create_allowed = False

        # Agent payment preparation creates the reservation and PENDING attempt
        # before checkout is launched. A never-submitted prepared attempt is
        # safe for its first order creation only when the durable handoff still
        # proves the exact owner, proposal, contract, reservation, and amount.
        # The ORDER_CREATE_ATTEMPT_STARTED event is committed below before any
        # provider request, so a concurrent request or a later retry will see
        # evidence and cannot enter this first-submission path again.
        agent_handoff = None
        agent_proposal = None
        if order_id is None and not claim.newly_claimed:
            agent_handoff = await db.scalar(select(AgentPaymentHandoffRecord).where(
                AgentPaymentHandoffRecord.attempt_id == attempt.id,
            ).with_for_update().execution_options(populate_existing=True))
            if agent_handoff is not None:
                agent_proposal = await db.scalar(select(AgentProposalRecord).where(
                    AgentProposalRecord.id == agent_handoff.proposal_id,
                    AgentProposalRecord.owner_id == actor_id,
                ).with_for_update().execution_options(populate_existing=True))

        valid_agent_handoff = False
        if agent_handoff is not None and agent_proposal is not None:
            now = datetime.now(timezone.utc)
            valid_agent_handoff = (
                agent_handoff.owner_id == actor_id
                and agent_handoff.contract_id == contract.id
                and agent_handoff.contract_version == contract.version
                and agent_handoff.reservation_id == reservation.id
                and agent_handoff.attempt_id == attempt.id
                and agent_proposal.owner_id == actor_id
                and agent_proposal.status == "CONFIRMED"
                and agent_proposal.policy_decision == "ALLOW"
                and agent_proposal.contract_id == contract.id
                and agent_proposal.contract_version == contract.version
                and agent_proposal.merchant_id == reservation.merchant_id
                and agent_proposal.proposed_amount == reservation.amount
                and agent_proposal.proposed_currency == reservation.currency
                and agent_proposal.created_at is not None
                and agent_proposal.created_at <= now
                and now - agent_proposal.created_at <= AGENT_PROPOSAL_MAX_AGE
            )
        if agent_handoff is not None and not valid_agent_handoff:
            raise PaymentOrchestrationError("Agent payment handoff is no longer authorized.")

        preparation_markers = [
            event for event in events
            if event.event_type == "CHECKOUT_NOT_STARTED"
        ]
        valid_preparation_provenance = (
            agent_handoff is not None
            and len(preparation_markers) == 1
            and preparation_markers[0].actor_id == actor_id
            and isinstance(preparation_markers[0].event_data, dict)
            and preparation_markers[0].event_data == {
                "handoff_id": str(agent_handoff.id),
                "proposal_id": str(agent_handoff.proposal_id),
                "reservation_id": str(agent_handoff.reservation_id),
                "provenance": "PAYMENT_PREPARED",
            }
        )

        if order_id is None and accepted is not None:
            candidate = accepted.event_data.get("provider_order_id") if isinstance(accepted.event_data, dict) else None
            if isinstance(candidate, str) and candidate.strip() and candidate == candidate.strip():
                recovery_order_id = candidate
            else:
                raise PaymentOrchestrationError(
                    "Accepted provider order evidence is invalid; review required.",
                    code="ORDER_RECOVERY_REQUIRED", status_code=409,
                )
        elif order_id is None and claim.newly_claimed:
            create_allowed = True
        elif order_id is None and valid_agent_handoff:
            latest_type = events[-1].event_type if events else None
            has_uncertain_evidence = any(event.event_type in {
                "ORDER_CREATE_OUTCOME_UNKNOWN", "ORDER_BINDING_FAILED",
            } for event in events)
            if not valid_preparation_provenance:
                raise PaymentOrchestrationError(
                    "Checkout provenance is missing for this prepared payment; review is required.",
                    code="CHECKOUT_PROVENANCE_MISSING", status_code=409,
                )
            if has_uncertain_evidence:
                raise PaymentOrchestrationError(
                    "Unknown provider outcome must be reviewed before retry.",
                    code="PROVIDER_OUTCOME_UNKNOWN", status_code=409,
                )
            if latest_type == "CHECKOUT_NOT_STARTED" and len(events) == 1:
                create_allowed = True
            elif latest_type in {"ORDER_CREATE_NOT_SUBMITTED", "ORDER_CREATE_REJECTED"}:
                create_allowed = True
            else:
                raise PaymentOrchestrationError(
                    "Previous checkout activity requires review before retry.",
                    code="PROVIDER_OUTCOME_UNKNOWN", status_code=409,
                )
        elif order_id is None:
            latest_type = events[-1].event_type if events else None
            if latest_type in {"ORDER_CREATE_NOT_SUBMITTED", "ORDER_CREATE_REJECTED"}:
                create_allowed = True
            else:
                # An unproven legacy attempt may have submitted a POST before
                # durable start events were introduced. Never infer safety
                # from a missing order ID or empty, unrelated local state.
                raise PaymentOrchestrationError(
                    "Order creation outcome requires review; retry blocked.",
                    code="PROVIDER_OUTCOME_UNKNOWN", status_code=409,
                )

        merchant_id, amount, currency = reservation.merchant_id, reservation.amount, reservation.currency
        provider_key = attempt.provider_idempotency_key

        if create_allowed:
            db.add(PaymentAttemptEventRecord(
                attempt_id=attempt.id, actor_id=actor_id,
                event_type="ORDER_CREATE_ATTEMPT_STARTED", event_correlation_id=uuid.uuid4(),
                event_data={"category": "ATTEMPT_STARTED"},
            ))
            await db.flush()

    try:
        merchant = registry.resolve(merchant_id)
    except MerchantRegistryError:
        if create_allowed:
            await _record_order_event(db, attempt_id=claim.attempt_id, actor_id=actor_id,
                event_type="ORDER_CREATE_NOT_SUBMITTED", data={"category": "LOCAL_MERCHANT_VALIDATION_FAILED"})
        raise
    if order_id is not None:
        order = await paypal.get_order(order_id=order_id,
            expected_paypal_merchant_id=merchant.paypal_merchant_id, amount=amount, currency=currency)
        return PaymentLaunch(claim.attempt_id, order_id, _approval_url(order), claim.status)

    if recovery_order_id is not None:
        # A validated acceptance event preserves the exact order identity.
        # Recover it with GET and bind that order; never POST create again.
        order = await paypal.get_order(order_id=recovery_order_id,
            expected_paypal_merchant_id=merchant.paypal_merchant_id, amount=amount, currency=currency)
        binding = await bind_provider_order(db, attempt_id=claim.attempt_id,
            provider_order_id=recovery_order_id)
        await _record_order_event(db, attempt_id=claim.attempt_id, actor_id=actor_id,
            event_type="ORDER_CREATE_BOUND", data={"provider_order_id": recovery_order_id})
        return PaymentLaunch(binding.attempt_id, binding.provider_order_id, _approval_url(order), "PENDING")

    order_kwargs = {}
    if return_url is not None and cancel_url is not None:
        order_kwargs = {
            "return_url": _checkout_url(return_url, claim.attempt_id),
            "cancel_url": _checkout_url(cancel_url, claim.attempt_id),
        }
    try:
        order = await paypal.create_order(amount=amount, currency=currency,
            provider_idempotency_key=provider_key,
            expected_paypal_merchant_id=merchant.paypal_merchant_id, **order_kwargs)
    except PayPalOrderNotSubmittedError:
        await _record_order_event(db, attempt_id=claim.attempt_id, actor_id=actor_id,
            event_type="ORDER_CREATE_NOT_SUBMITTED", data={"category": "NOT_SUBMITTED"})
        raise
    except PayPalOrderRejectedError as exc:
        await _record_order_event(db, attempt_id=claim.attempt_id, actor_id=actor_id,
            event_type="ORDER_CREATE_REJECTED", data={"category": "PROVIDER_REJECTED", "http_status": exc.status_code})
        raise
    except PayPalOrderOutcomeUnknownError as exc:
        data = {"category": "OUTCOME_UNKNOWN"}
        if exc.status_code is not None:
            data["provider_http_status"] = exc.status_code
        await _record_order_event(db, attempt_id=claim.attempt_id, actor_id=actor_id,
            event_type="ORDER_CREATE_OUTCOME_UNKNOWN", data=data)
        raise
    except PayPalSandboxError:
        await _record_order_event(db, attempt_id=claim.attempt_id, actor_id=actor_id,
            event_type="ORDER_CREATE_OUTCOME_UNKNOWN", data={"category": "OUTCOME_UNKNOWN"})
        raise

    try:
        validate_paypal_order(order, order_id=None,
            expected_paypal_merchant_id=merchant.paypal_merchant_id, amount=amount, currency=currency)
    except PayPalSandboxError:
        await _record_order_event(db, attempt_id=claim.attempt_id, actor_id=actor_id,
            event_type="ORDER_CREATE_OUTCOME_UNKNOWN", data={"category": "UNVERIFIED_PROVIDER_RESPONSE"})
        raise PayPalOrderOutcomeUnknownError("Provider order response could not be verified.")

    provider_order_id = order["id"]
    await _record_order_event(db, attempt_id=claim.attempt_id, actor_id=actor_id,
        event_type="ORDER_CREATE_PROVIDER_ACCEPTED",
        data={"category": "PROVIDER_ACCEPTED", "provider_order_id": provider_order_id})
    try:
        binding = await bind_provider_order(db, attempt_id=claim.attempt_id,
            provider_order_id=provider_order_id)
    except Exception as exc:
        await _record_order_event(db, attempt_id=claim.attempt_id, actor_id=actor_id,
            event_type="ORDER_BINDING_FAILED", data={"category": "LOCAL_BINDING_FAILED"})
        raise PaymentOrchestrationError(
            "Provider order was accepted; local binding requires safe recovery.",
            code="ORDER_BINDING_RECOVERY_REQUIRED", status_code=409,
        ) from exc
    await _record_order_event(db, attempt_id=claim.attempt_id, actor_id=actor_id,
        event_type="ORDER_CREATE_BOUND", data={"provider_order_id": binding.provider_order_id})
    return PaymentLaunch(binding.attempt_id, binding.provider_order_id, _approval_url(order), "PENDING")


async def _record_order_event(db: AsyncSession, *, attempt_id: uuid.UUID,
                              actor_id: uuid.UUID, event_type: str, data: dict) -> None:
    """Persist sanitized order lifecycle evidence in its own short transaction."""
    async with db.begin():
        attempt_ref = await db.get(PaymentAttemptRecord, attempt_id)
        reservation_ref = await db.get(PaymentReservationRecord, attempt_ref.reservation_id) if attempt_ref else None
        if attempt_ref is None or reservation_ref is None:
            raise PaymentOrchestrationError("Payment attempt is unavailable for diagnostics.")
        contract = await db.scalar(select(IntentContractRecord).where(
            IntentContractRecord.id == reservation_ref.contract_id,
        ).with_for_update().execution_options(populate_existing=True))
        reservation = await db.scalar(select(PaymentReservationRecord).where(
            PaymentReservationRecord.id == reservation_ref.id,
        ).with_for_update().execution_options(populate_existing=True))
        attempt = await db.scalar(select(PaymentAttemptRecord).where(
            PaymentAttemptRecord.id == attempt_id,
        ).with_for_update().execution_options(populate_existing=True))
        if contract is None or reservation is None or attempt is None or reservation.actor_id != actor_id:
            raise PaymentOrchestrationError("Payment attempt is unavailable for diagnostics.")
        db.add(PaymentAttemptEventRecord(
            attempt_id=attempt_id, actor_id=actor_id, event_type=event_type,
            event_correlation_id=uuid.uuid4(), event_data=data,
        ))
        await db.flush()


async def capture_buyer_approved_order(
    db: AsyncSession, *, attempt_id: uuid.UUID, actor_id: uuid.UUID,
    registry: TrustedMerchantRegistry, paypal: PayPalSandboxClient,
) -> str:
    try:
        result = await capture_approved_payment(db, attempt_id=attempt_id,
            actor_id=actor_id, registry=registry, paypal=paypal)
    except PaymentCaptureError as exc:
        raise PaymentOrchestrationError(str(exc)) from exc
    return result.state
