import uuid
import hashlib
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from intentra.models.agent_proposal import AgentProposalEventRecord, AgentProposalRecord
from intentra.models.intent_contract import IntentContractRecord, UserRecord
from intentra.models.payment_reservation import PaymentReservationRecord
from intentra.services.agent_provider import (
    AgentProviderError, ExtractedPurchase, PurchasePlanningProvider,
    validate_extraction_evidence,
)
from pydantic import ValidationError
from intentra.services.authorization import Decision, IntentContract, PaymentProposal, authorize
from intentra.services.merchant_registry import MerchantRegistryError, TrustedMerchantRegistry
from intentra.services.proposal_diagnostics import log as diagnostic_log

SUPPORTED_CURRENCIES = {"USD", "CAD", "EUR", "GBP", "AUD", "JPY"}

ACTIVE_BUDGET_STATUSES = ("RESERVED", "EXECUTION_PENDING", "OUTCOME_UNKNOWN", "CAPTURED")
MAX_PROPOSALS_PER_WINDOW = 10
RATE_WINDOW = timedelta(minutes=5)


class AgentProposalError(Exception):
    def __init__(self, message: str, status_code: int = 409):
        self.status_code = status_code
        super().__init__(message)


@dataclass(frozen=True)
class PolicyResult:
    decision: str
    reason: str
    status: str
    contract_version: int | None
    merchant_id: str | None
    amount: Decimal | None
    currency: str | None
    missing: list[str]


@dataclass(frozen=True)
class ProposalCreateResult:
    proposal: AgentProposalRecord
    created: bool


def _event(proposal_id: uuid.UUID, actor_id: uuid.UUID | None, event_type: str, data: dict | None = None) -> AgentProposalEventRecord:
    return AgentProposalEventRecord(
        proposal_id=proposal_id,
        actor_id=actor_id,
        event_type=event_type,
        correlation_id=uuid.uuid4(),
        event_data=data or {},
    )


async def _policy(db: AsyncSession, *, owner_id: uuid.UUID, contract_id: uuid.UUID | None,
                  extraction: ExtractedPurchase, registry: TrustedMerchantRegistry | None) -> PolicyResult:
    missing = []
    if extraction.amount is None:
        missing.append("amount")
    if extraction.currency is None:
        missing.append("currency")
    if extraction.purpose is None:
        missing.append("purchase purpose")
    if extraction.currency is not None and extraction.currency not in SUPPORTED_CURRENCIES:
        return PolicyResult("DENY", "Currency is not supported by INTENTRA payment policy.", "READY_FOR_REVIEW",
                            None, extraction.merchant_id, extraction.amount, extraction.currency, [])
    if contract_id is None:
        missing.append("approved contract")
    contract = None
    if contract_id is not None:
        contract = await db.scalar(select(IntentContractRecord).where(
            IntentContractRecord.id == contract_id,
            IntentContractRecord.owner_id == owner_id,
        ))
        if contract is None:
            # Treat an unowned/nonexistent ID identically; do not reveal existence.
            return PolicyResult("DENY", "Selected contract is unavailable to this account.", "READY_FOR_REVIEW", None,
                                extraction.merchant_id, extraction.amount, extraction.currency, [])
        if extraction.merchant_id is None:
            # Explicit contract selection supplies a human-authorized merchant scope.
            merchant_id = contract.merchant_id
        else:
            merchant_id = extraction.merchant_id
        if extraction.amount is None or extraction.currency is None or extraction.purpose is None:
            return PolicyResult("NEEDS_INFORMATION", "Provide an explicit purchase purpose, amount, and currency.", "NEEDS_INFORMATION",
                                contract.version, merchant_id, extraction.amount, extraction.currency, missing)
        if registry is None:
            return PolicyResult("NEEDS_INFORMATION", "Trusted merchant registry is not configured.",
                                "NEEDS_INFORMATION", contract.version, merchant_id, extraction.amount,
                                extraction.currency, ["trusted merchant registry"])
        try:
            registry.resolve(merchant_id or "")
        except MerchantRegistryError:
            return PolicyResult("DENY", "Merchant is not registered as trusted for payment policy.",
                                "READY_FOR_REVIEW", contract.version, merchant_id, extraction.amount,
                                extraction.currency, [])
        result = authorize(
            IntentContract(contract.merchant_id, contract.maximum_amount, contract.currency, contract.status == "APPROVED"),
            PaymentProposal(merchant_id or "", extraction.amount, extraction.currency),
        )
        if result.decision != Decision.ALLOW:
            return PolicyResult("DENY", result.reason, "READY_FOR_REVIEW", contract.version, merchant_id,
                                extraction.amount, extraction.currency, [])
        spent = await db.scalar(select(func.coalesce(func.sum(PaymentReservationRecord.amount), 0)).where(
            PaymentReservationRecord.contract_id == contract.id,
            PaymentReservationRecord.status.in_(ACTIVE_BUDGET_STATUSES),
        ))
        remaining = contract.maximum_amount - Decimal(spent or 0)
        if extraction.amount > remaining:
            return PolicyResult("DENY", "Purchase exceeds the available contract budget.", "READY_FOR_REVIEW",
                                contract.version, merchant_id, extraction.amount, extraction.currency, [])
        return PolicyResult("ALLOW", "Purchase details fit the current approved contract and available budget.",
                            "READY_FOR_REVIEW", contract.version, merchant_id, extraction.amount,
                            extraction.currency, [])
    missing.extend(["merchant identifier", "contract selection"])
    return PolicyResult("NEEDS_INFORMATION", "Select an approved contract and provide purchase details.",
                        "NEEDS_INFORMATION", None, extraction.merchant_id, extraction.amount,
                        extraction.currency, list(dict.fromkeys(missing)))


async def _apply_evaluation(db: AsyncSession, proposal: AgentProposalRecord, actor_id: uuid.UUID,
                            extracted: ExtractedPurchase, registry: TrustedMerchantRegistry | None) -> AgentProposalRecord:
    result = await _policy(db, owner_id=actor_id, contract_id=proposal.contract_id,
                           extraction=extracted, registry=registry)
    proposal.requested_purpose = extracted.purpose
    proposal.merchant_id = result.merchant_id
    proposal.proposed_amount = result.amount
    proposal.proposed_currency = result.currency
    proposal.contract_version = result.contract_version
    proposal.policy_decision = result.decision
    proposal.policy_reason = result.reason
    proposal.missing_information = result.missing
    proposal.status = result.status
    proposal.explanation = "Extracted purchase details are untrusted until the owner reviews them."
    proposal.version += 1
    proposal.updated_at = datetime.now(timezone.utc)
    db.add(_event(proposal.id, actor_id, "PROPOSAL_EVALUATED", {
        "decision": result.decision, "contract_version": result.contract_version,
        "status": result.status,
    }))
    return proposal


async def create_proposal(db: AsyncSession, *, owner_id: uuid.UUID, request_text: str,
                          contract_id: uuid.UUID | None, provider: PurchasePlanningProvider,
                          registry: TrustedMerchantRegistry | None,
                          idempotency_key: uuid.UUID) -> ProposalCreateResult:
    # The owner lock serializes idempotency-key claims without being held over
    # the external model request. Only hashes are stored in immutable history.
    idempotency_hash = hashlib.sha256(idempotency_key.bytes).hexdigest()
    request_fingerprint = hashlib.sha256(
        (str(contract_id or "") + "\0" + request_text).encode("utf-8")
    ).hexdigest()
    async with db.begin():
        user = await db.scalar(select(UserRecord).where(UserRecord.id == owner_id).with_for_update())
        if user is None:
            raise AgentProposalError("Account unavailable.", 401)
        prior = (await db.execute(
            select(AgentProposalEventRecord, AgentProposalRecord)
            .join(AgentProposalRecord, AgentProposalRecord.id == AgentProposalEventRecord.proposal_id)
            .where(
                AgentProposalRecord.owner_id == owner_id,
                AgentProposalEventRecord.event_type == "PROPOSAL_CREATED",
                AgentProposalEventRecord.event_data["idempotency_hash"].astext == idempotency_hash,
            )
            .limit(1)
        )).one_or_none()
        if prior is not None:
            prior_event, prior_proposal = prior
            if prior_event.event_data.get("request_fingerprint") != request_fingerprint:
                raise AgentProposalError("Idempotency key was already used for a different request.", 409)
            failed = await db.scalar(select(AgentProposalEventRecord.id).where(
                AgentProposalEventRecord.proposal_id == prior_proposal.id,
                AgentProposalEventRecord.event_type == "PROPOSAL_GENERATION_FAILED",
            ).limit(1))
            if prior_proposal.status == "DRAFT":
                if failed:
                    raise AgentProposalError(
                        "Proposal generation failed. Submit again to start a new request.", 503
                    )
                raise AgentProposalError("This proposal request is already being processed.", 409)
            return ProposalCreateResult(prior_proposal, False)
        cutoff = datetime.now(timezone.utc) - RATE_WINDOW
        count = await db.scalar(select(func.count(AgentProposalRecord.id)).where(
            AgentProposalRecord.owner_id == owner_id,
            AgentProposalRecord.created_at >= cutoff,
        ))
        if (count or 0) >= MAX_PROPOSALS_PER_WINDOW:
            raise AgentProposalError("Too many purchase planning requests. Try again later.", 429)
        proposal = AgentProposalRecord(
            owner_id=owner_id,
            natural_language_request=request_text,
            contract_id=contract_id,
            status="DRAFT",
            provider_mode=provider.mode,
            version=1,
        )
        db.add(proposal)
        await db.flush()
        db.add(_event(proposal.id, owner_id, "PROPOSAL_CREATED", {
            "provider_mode": provider.mode,
            "idempotency_hash": idempotency_hash,
            "request_fingerprint": request_fingerprint,
        }))
    generation_started = time.monotonic()
    diagnostic_log("proposal_generation_started", provider_mode=provider.mode, stage="generation")
    try:
        extracted = await provider.extract(request_text)
        if isinstance(extracted, ExtractedPurchase):
            extracted = ExtractedPurchase.model_validate(extracted.model_dump())
        else:
            extracted = ExtractedPurchase.model_validate(extracted)
        validate_extraction_evidence(request_text, extracted)
    except ValidationError:
        async with db.begin():
            current = await db.scalar(select(AgentProposalRecord).where(AgentProposalRecord.id == proposal.id).with_for_update())
            db.add(_event(proposal.id, owner_id, "PROPOSAL_GENERATION_FAILED", {"provider_mode": provider.mode}))
            if current:
                current.version += 1
                current.updated_at = datetime.now(timezone.utc)
        diagnostic_log("proposal_generation_failed", provider_mode=provider.mode, stage="validation",
                       elapsed_ms=int((time.monotonic() - generation_started) * 1000),
                       error_code="EXTRACTION_VALIDATION_FAILED")
        raise AgentProposalError("Purchase proposal generation is unavailable. Your request was not evaluated.", 503) from None
    except AgentProviderError as exc:
        async with db.begin():
            current = await db.scalar(select(AgentProposalRecord).where(AgentProposalRecord.id == proposal.id).with_for_update())
            db.add(_event(proposal.id, owner_id, "PROPOSAL_GENERATION_FAILED", {"provider_mode": provider.mode}))
            if current:
                current.version += 1
                current.updated_at = datetime.now(timezone.utc)
        diagnostic_log("proposal_generation_failed", provider_mode=provider.mode, stage="provider",
                       elapsed_ms=int((time.monotonic() - generation_started) * 1000), error_code=exc.code)
        raise AgentProposalError("Purchase proposal generation is unavailable. Your request was not evaluated.", 503) from None
    diagnostic_log("proposal_generation_completed", provider_mode=provider.mode, stage="generation",
                   elapsed_ms=int((time.monotonic() - generation_started) * 1000))
    async with db.begin():
        if proposal.contract_id is not None:
            await db.scalar(select(IntentContractRecord).where(
                IntentContractRecord.id == proposal.contract_id,
                IntentContractRecord.owner_id == owner_id,
            ).with_for_update())
        current = await db.scalar(select(AgentProposalRecord).where(
            AgentProposalRecord.id == proposal.id, AgentProposalRecord.owner_id == owner_id,
        ).with_for_update())
        if current is None or current.status != "DRAFT":
            raise AgentProposalError("Proposal state changed during generation.")
        await _apply_evaluation(db, current, owner_id, extracted, registry)
    await db.refresh(proposal)
    return ProposalCreateResult(proposal, True)


async def get_proposal(db: AsyncSession, *, owner_id: uuid.UUID, proposal_id: uuid.UUID) -> AgentProposalRecord:
    proposal = await db.scalar(select(AgentProposalRecord).where(
        AgentProposalRecord.id == proposal_id, AgentProposalRecord.owner_id == owner_id,
    ))
    if proposal is None:
        raise AgentProposalError("Proposal not found.", 404)
    return proposal


async def list_proposals(db: AsyncSession, *, owner_id: uuid.UUID) -> list[AgentProposalRecord]:
    return list((await db.scalars(select(AgentProposalRecord).where(
        AgentProposalRecord.owner_id == owner_id,
    ).order_by(AgentProposalRecord.created_at.desc(), AgentProposalRecord.id.desc()).limit(100))).all())


async def reevaluate_proposal(db: AsyncSession, *, owner_id: uuid.UUID, proposal_id: uuid.UUID,
                              registry: TrustedMerchantRegistry | None) -> AgentProposalRecord:
    async with db.begin():
        snapshot = await db.scalar(select(AgentProposalRecord).where(
            AgentProposalRecord.id == proposal_id, AgentProposalRecord.owner_id == owner_id,
        ))
        if snapshot is None:
            raise AgentProposalError("Proposal not found.", 404)
        contract_id = snapshot.contract_id
        if contract_id:
            await db.scalar(select(IntentContractRecord).where(
                IntentContractRecord.id == contract_id,
                IntentContractRecord.owner_id == owner_id,
            ).with_for_update())
        current = await db.scalar(select(AgentProposalRecord).where(
            AgentProposalRecord.id == proposal_id, AgentProposalRecord.owner_id == owner_id,
        ).with_for_update())
        if current.status in {"CONFIRMED", "REJECTED"}:
            raise AgentProposalError("This proposal can no longer be evaluated.")
        extracted = ExtractedPurchase(purpose=current.requested_purpose, merchant_id=current.merchant_id,
                                      amount=current.proposed_amount, currency=current.proposed_currency)
        await _apply_evaluation(db, current, owner_id, extracted, registry)
    await db.refresh(current)
    return current


async def confirm_proposal(db: AsyncSession, *, owner_id: uuid.UUID, proposal_id: uuid.UUID,
                           registry: TrustedMerchantRegistry | None) -> AgentProposalRecord:
    snapshot = await get_proposal(db, owner_id=owner_id, proposal_id=proposal_id)
    contract_id = snapshot.contract_id
    await db.rollback()
    async with db.begin():
        if contract_id:
            contract = await db.scalar(select(IntentContractRecord).where(
                IntentContractRecord.id == contract_id,
                IntentContractRecord.owner_id == owner_id,
            ).with_for_update())
        else:
            contract = None
        current = await db.scalar(select(AgentProposalRecord).where(
            AgentProposalRecord.id == proposal_id, AgentProposalRecord.owner_id == owner_id,
        ).with_for_update())
        if current is None:
            raise AgentProposalError("Proposal not found.", 404)
        if current.status == "CONFIRMED":
            return current
        if current.status != "READY_FOR_REVIEW" or current.policy_decision != "ALLOW":
            raise AgentProposalError("Only a currently allowed proposal can be confirmed.")
        if contract is None or contract.status != "APPROVED" or contract.version != current.contract_version:
            raise AgentProposalError("Contract authorization changed; evaluate the proposal again.")
        if current.merchant_id != contract.merchant_id or current.proposed_currency != contract.currency:
            raise AgentProposalError("Proposal no longer matches the approved contract.")
        if registry is None:
            raise AgentProposalError("Trusted merchant registry is unavailable; proposal cannot be confirmed.")
        try:
            registry.resolve(contract.merchant_id)
        except MerchantRegistryError:
            raise AgentProposalError("Merchant is no longer trusted; proposal cannot be confirmed.") from None
        spent = await db.scalar(select(func.coalesce(func.sum(PaymentReservationRecord.amount), 0)).where(
            PaymentReservationRecord.contract_id == contract.id,
            PaymentReservationRecord.status.in_(ACTIVE_BUDGET_STATUSES),
        ))
        if current.proposed_amount is None or current.proposed_amount > contract.maximum_amount - Decimal(spent or 0):
            raise AgentProposalError("Available contract budget changed; evaluate the proposal again.")
        current.status = "CONFIRMED"
        current.version += 1
        current.updated_at = datetime.now(timezone.utc)
        db.add(_event(current.id, owner_id, "PROPOSAL_CONFIRMED", {"contract_id": str(contract.id), "contract_version": contract.version}))
    await db.refresh(current)
    return current


async def reject_proposal(db: AsyncSession, *, owner_id: uuid.UUID, proposal_id: uuid.UUID,
                          reason: str | None = None) -> AgentProposalRecord:
    reason = reason.strip() if reason is not None else None
    if reason is not None and (not reason or len(reason) > 500):
        raise AgentProposalError("Rejection reason must contain 1 to 500 characters.", 422)
    snapshot = await get_proposal(db, owner_id=owner_id, proposal_id=proposal_id)
    contract_id = snapshot.contract_id
    prior_status = snapshot.status
    await db.rollback()
    async with db.begin():
        if contract_id:
            await db.scalar(select(IntentContractRecord).where(
                IntentContractRecord.id == contract_id,
                IntentContractRecord.owner_id == owner_id,
            ).with_for_update())
        current = await db.scalar(select(AgentProposalRecord).where(
            AgentProposalRecord.id == proposal_id, AgentProposalRecord.owner_id == owner_id,
        ).with_for_update())
        if current.status == "REJECTED":
            return current
        if current.status == "CONFIRMED":
            raise AgentProposalError("A confirmed proposal cannot be rejected.")
        current.status = "REJECTED"
        current.version += 1
        current.updated_at = datetime.now(timezone.utc)
        event_data = {"prior_status": prior_status}
        if reason is not None:
            event_data["reason"] = reason
        db.add(_event(current.id, owner_id, "PROPOSAL_REJECTED", event_data))
    await db.refresh(current)
    return current
