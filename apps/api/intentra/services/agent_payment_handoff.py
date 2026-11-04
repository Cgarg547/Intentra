"""Owner-triggered, local-only handoff from a confirmed proposal to payment state."""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from intentra.models.agent_payment_handoff import AgentPaymentHandoffRecord
from intentra.models.agent_proposal import AgentProposalEventRecord, AgentProposalRecord
from intentra.models.intent_contract import IntentContractRecord
from intentra.models.payment_evaluation import PaymentEvaluationRecord
from intentra.models.payment_attempt_event import PaymentAttemptEventRecord
from intentra.models.payment_reservation import PaymentReservationRecord
from intentra.services.agent_proposals import AgentProposalError
from intentra.services.merchant_registry import MerchantRegistryError, TrustedMerchantRegistry
from intentra.services.payment_execution import claim_payment_execution_locked
from intentra.services.payment_reservation import PaymentReservationError, reserve_payment_locked

PROPOSAL_MAX_AGE = timedelta(hours=24)
SUPPORTED_CURRENCIES = {"USD", "CAD", "EUR", "GBP", "AUD", "JPY"}


async def prepare_proposal_payment(
    db: AsyncSession,
    *,
    owner_id: uuid.UUID,
    proposal_id: uuid.UUID,
    registry: TrustedMerchantRegistry | None,
) -> AgentPaymentHandoffRecord:
    """Reserve and claim the confirmed proposal atomically; never calls PayPal."""
    snapshot = await db.scalar(select(AgentProposalRecord).where(
        AgentProposalRecord.id == proposal_id,
        AgentProposalRecord.owner_id == owner_id,
    ))
    if snapshot is None:
        await db.rollback()
        raise AgentProposalError("Proposal not found.", 404)
    contract_id = snapshot.contract_id
    await db.rollback()
    if contract_id is None:
        raise AgentProposalError("Proposal has no authorized contract.")

    try:
        async with db.begin():
            # Preserve the financial lock order: contract, then reservation,
            # then attempt. Proposal is locked immediately after its contract.
            contract = await db.scalar(select(IntentContractRecord).where(
                IntentContractRecord.id == contract_id,
                IntentContractRecord.owner_id == owner_id,
            ).with_for_update().execution_options(populate_existing=True))
            proposal = await db.scalar(select(AgentProposalRecord).where(
                AgentProposalRecord.id == proposal_id,
                AgentProposalRecord.owner_id == owner_id,
            ).with_for_update().execution_options(populate_existing=True))
            if proposal is None:
                raise AgentProposalError("Proposal not found.", 404)

            existing = await db.scalar(select(AgentPaymentHandoffRecord).where(
                AgentPaymentHandoffRecord.proposal_id == proposal.id,
                AgentPaymentHandoffRecord.owner_id == owner_id,
            ))
            if existing is not None:
                return existing

            now = datetime.now(timezone.utc)
            if proposal.status != "CONFIRMED" or proposal.policy_decision != "ALLOW":
                raise AgentProposalError("Only an owner-confirmed, policy-eligible proposal can be prepared.")
            if contract is None or contract.status != "APPROVED":
                raise AgentProposalError("Contract authorization is no longer active.")
            if proposal.contract_id != contract.id or proposal.contract_version != contract.version:
                raise AgentProposalError("Contract version changed; evaluate and confirm a current proposal.")
            if proposal.created_at is None or now - proposal.created_at > PROPOSAL_MAX_AGE:
                raise AgentProposalError("Proposal expired; create and review a current proposal.")
            if (proposal.merchant_id is None or proposal.proposed_amount is None
                or proposal.proposed_currency is None or proposal.proposed_amount <= 0):
                raise AgentProposalError("Proposal payment details are incomplete.")
            if proposal.proposed_currency not in SUPPORTED_CURRENCIES:
                raise AgentProposalError("Proposal currency is not supported.")
            if (proposal.merchant_id != contract.merchant_id
                or proposal.proposed_currency != contract.currency):
                raise AgentProposalError("Proposal no longer matches its approved contract.")
            if registry is None:
                raise AgentProposalError("Trusted merchant registry is unavailable.", 503)
            try:
                registry.resolve(contract.merchant_id)
            except MerchantRegistryError:
                raise AgentProposalError("Merchant is no longer trusted.") from None

            try:
                reservation, _, _ = await reserve_payment_locked(
                    db,
                    contract=contract,
                    actor_id=owner_id,
                    idempotency_key=f"agent-proposal-{proposal.id}",
                    merchant_id=proposal.merchant_id,
                    amount=Decimal(proposal.proposed_amount),
                    currency=proposal.proposed_currency,
                    require_allow=True,
                )
            except PaymentReservationError as exc:
                raise AgentProposalError(str(exc), exc.status_code) from exc
            if reservation.status != "RESERVED":
                raise AgentProposalError("Payment is not eligible for reservation.")

            # Explicitly lock the reservation before the attempt claim, matching
            # the execution service's contract -> reservation -> attempt order.
            reservation = await db.scalar(select(PaymentReservationRecord).where(
                PaymentReservationRecord.id == reservation.id,
                PaymentReservationRecord.actor_id == owner_id,
            ).with_for_update().execution_options(populate_existing=True))
            if reservation is None:
                raise AgentProposalError("Payment reservation is unavailable.")
            claim = await claim_payment_execution_locked(
                db, contract=contract, reservation=reservation, actor_id=owner_id
            )
            if claim.status != "PENDING":
                raise AgentProposalError("Existing payment attempt is not eligible for checkout.")

            db.add(PaymentEvaluationRecord(
                contract_id=contract.id,
                actor_id=owner_id,
                contract_version=contract.version,
                merchant_id=proposal.merchant_id,
                amount=proposal.proposed_amount,
                currency=proposal.proposed_currency,
                decision="ALLOW",
                reason="Owner-confirmed proposal passed current payment policy and budget evaluation.",
            ))
            handoff = AgentPaymentHandoffRecord(
                proposal_id=proposal.id,
                owner_id=owner_id,
                contract_id=contract.id,
                contract_version=contract.version,
                reservation_id=reservation.id,
                attempt_id=claim.attempt_id,
            )
            db.add(handoff)
            await db.flush()
            db.add(PaymentAttemptEventRecord(
                attempt_id=claim.attempt_id,
                actor_id=owner_id,
                event_type="CHECKOUT_NOT_STARTED",
                event_correlation_id=uuid.uuid4(),
                event_data={
                    "handoff_id": str(handoff.id),
                    "proposal_id": str(proposal.id),
                    "reservation_id": str(reservation.id),
                    "provenance": "PAYMENT_PREPARED",
                },
            ))
            db.add(AgentProposalEventRecord(
                proposal_id=proposal.id,
                actor_id=owner_id,
                event_type="PROPOSAL_PAYMENT_PREPARED",
                correlation_id=uuid.uuid4(),
                event_data={
                    "contract_id": str(contract.id),
                    "contract_version": contract.version,
                    "reservation_id": str(reservation.id),
                    "attempt_id": str(claim.attempt_id),
                },
            ))
            await db.flush()
            return handoff
    except AgentProposalError:
        raise
