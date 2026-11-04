import uuid
import asyncio
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from intentra.database import get_db
from intentra.models.agent_proposal import AgentProposalEventRecord
from intentra.models.agent_payment_handoff import AgentPaymentHandoffRecord
from intentra.models.payment_reservation import PaymentReservationRecord
from intentra.models.intent_contract import UserRecord
from intentra.routes.auth import current_user
from intentra.schemas.agent_proposals import (
    PaymentPreparationResponse, ProposalCreateRequest, ProposalEventResponse,
    ProposalListResponse, ProposalResponse, ProposalRejectRequest,
)
from intentra.services.agent_provider import AgentProviderError, get_purchase_planning_provider
from intentra.services.merchant_registry import MerchantRegistryError, TrustedMerchantRegistry, load_trusted_merchant_registry
from intentra.services.agent_proposals import (
    AgentProposalError, confirm_proposal, create_proposal, get_proposal,
    list_proposals, reevaluate_proposal, reject_proposal,
)
from intentra.services.agent_payment_handoff import prepare_proposal_payment
from intentra.services.proposal_diagnostics import log as diagnostic_log, proposal_correlation_id

router = APIRouter(prefix="/api/agents", tags=["AI Purchase Planning"])
logger = logging.getLogger(__name__)


def agent_provider_dependency():
    try:
        return get_purchase_planning_provider()
    except AgentProviderError as exc:
        raise HTTPException(status_code=503, detail="Purchase planning provider is unavailable.") from exc


def agent_registry_dependency() -> TrustedMerchantRegistry | None:
    try:
        return load_trusted_merchant_registry()
    except MerchantRegistryError:
        # Policy will remain NEEDS_INFORMATION and cannot be confirmed.
        return None


async def _response(db: AsyncSession, proposal, *, include_events: bool = True,
                    event_rows: list[AgentProposalEventRecord] | None = None) -> ProposalResponse:
    handoff = await db.scalar(select(AgentPaymentHandoffRecord).where(
        AgentPaymentHandoffRecord.proposal_id == proposal.id,
        AgentPaymentHandoffRecord.owner_id == proposal.owner_id,
    ))
    reservation = await db.get(PaymentReservationRecord, handoff.reservation_id) if handoff else None
    events = []
    if include_events:
        if event_rows is None:
            event_rows = list((await db.scalars(select(AgentProposalEventRecord).where(
                AgentProposalEventRecord.proposal_id == proposal.id,
            ).order_by(AgentProposalEventRecord.created_at, AgentProposalEventRecord.id))).all())
        events = [ProposalEventResponse(event_type=row.event_type, actor_id=row.actor_id,
            event_data={key: value for key, value in row.event_data.items()
                        if key not in {"idempotency_hash", "request_fingerprint"}},
            created_at=row.created_at) for row in event_rows]
    return ProposalResponse(
        proposal_id=proposal.id, owner_id=proposal.owner_id,
        request=proposal.natural_language_request, requested_purpose=proposal.requested_purpose,
        merchant_id=proposal.merchant_id, proposed_amount=proposal.proposed_amount,
        currency=proposal.proposed_currency, contract_id=proposal.contract_id,
        contract_version=proposal.contract_version, explanation=proposal.explanation,
        missing_information=proposal.missing_information, policy_decision=proposal.policy_decision,
        policy_reason=proposal.policy_reason, status=proposal.status,
        provider_mode=proposal.provider_mode, version=proposal.version,
        created_at=proposal.created_at, updated_at=proposal.updated_at,
        payment_preparation=(PaymentPreparationResponse(
            reservation_id=handoff.reservation_id,
            attempt_id=handoff.attempt_id,
            contract_version=handoff.contract_version,
            created_at=handoff.created_at,
            status=reservation.status if reservation else "UNKNOWN",
        ) if handoff else None),
        events=events,
    )


def _raise(exc: AgentProposalError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/proposals", response_model=ProposalResponse, status_code=201)
async def submit_proposal(payload: ProposalCreateRequest,
                          response: Response,
                          idempotency_key: uuid.UUID = Header(alias="Idempotency-Key"),
                          correlation_id: str | None = Header(default=None, alias="X-Correlation-ID"),
                          user: UserRecord = Depends(current_user),
                          provider=Depends(agent_provider_dependency),
                          registry: TrustedMerchantRegistry | None = Depends(agent_registry_dependency),
                          db: AsyncSession = Depends(get_db)):
    try:
        correlation_id = str(uuid.UUID(correlation_id)) if correlation_id else str(uuid.uuid4())
    except (ValueError, AttributeError):
        correlation_id = str(uuid.uuid4())
    response.headers["X-Correlation-ID"] = correlation_id
    token = proposal_correlation_id.set(correlation_id)
    owner_id = user.id
    await db.rollback()
    try:
        result = await create_proposal(db, owner_id=owner_id, request_text=payload.request,
                                         contract_id=payload.contract_id, provider=provider, registry=registry,
                                         idempotency_key=idempotency_key)
        response.status_code = 201 if result.created else 200
        proposal = result.proposal
        try:
            return await _response(db, proposal)
        except asyncio.CancelledError:
            diagnostic_log("proposal_request_cancelled", provider_mode=provider.mode, stage="response")
            raise
        except Exception:
            diagnostic_log("proposal_request_failed", provider_mode=provider.mode, stage="response",
                           error_code="RESPONSE_CONSTRUCTION_FAILED")
            raise
    except AgentProposalError as exc:
        _raise(exc)
    except asyncio.CancelledError:
        diagnostic_log("proposal_request_cancelled", provider_mode=provider.mode, stage="request")
        raise
    except Exception:
        diagnostic_log("proposal_request_failed", provider_mode=provider.mode, stage="persistence",
                       error_code="PERSISTENCE_FAILED")
        raise
    finally:
        proposal_correlation_id.reset(token)


@router.get("/proposals", response_model=ProposalListResponse)
async def proposals(user: UserRecord = Depends(current_user), db: AsyncSession = Depends(get_db)):
    records = await list_proposals(db, owner_id=user.id)
    event_groups: dict[uuid.UUID, list[AgentProposalEventRecord]] = {}
    if records:
        event_rows = (await db.scalars(select(AgentProposalEventRecord).where(
            AgentProposalEventRecord.proposal_id.in_([item.id for item in records]),
        ).order_by(AgentProposalEventRecord.created_at, AgentProposalEventRecord.id))).all()
        for row in event_rows:
            event_groups.setdefault(row.proposal_id, []).append(row)
    return ProposalListResponse(items=[await _response(db, item, event_rows=event_groups.get(item.id, []))
        for item in records])


@router.get("/proposals/{proposal_id}", response_model=ProposalResponse)
async def proposal_detail(proposal_id: uuid.UUID, user: UserRecord = Depends(current_user),
                          db: AsyncSession = Depends(get_db)):
    try:
        record = await get_proposal(db, owner_id=user.id, proposal_id=proposal_id)
    except AgentProposalError as exc:
        _raise(exc)
    return await _response(db, record)


@router.post("/proposals/{proposal_id}/evaluate", response_model=ProposalResponse)
async def evaluate_proposal(proposal_id: uuid.UUID, user: UserRecord = Depends(current_user),
                            registry: TrustedMerchantRegistry | None = Depends(agent_registry_dependency),
                            db: AsyncSession = Depends(get_db)):
    owner_id = user.id
    await db.rollback()
    try:
        record = await reevaluate_proposal(db, owner_id=owner_id, proposal_id=proposal_id, registry=registry)
    except AgentProposalError as exc:
        _raise(exc)
    return await _response(db, record)


@router.post("/proposals/{proposal_id}/confirm", response_model=ProposalResponse)
async def confirm(proposal_id: uuid.UUID, user: UserRecord = Depends(current_user),
                  registry: TrustedMerchantRegistry | None = Depends(agent_registry_dependency),
                  db: AsyncSession = Depends(get_db)):
    owner_id = user.id
    await db.rollback()
    try:
        record = await confirm_proposal(db, owner_id=owner_id, proposal_id=proposal_id, registry=registry)
    except AgentProposalError as exc:
        _raise(exc)
    return await _response(db, record)


@router.post("/proposals/{proposal_id}/reject", response_model=ProposalResponse)
async def reject(proposal_id: uuid.UUID, payload: ProposalRejectRequest = ProposalRejectRequest(),
                 user: UserRecord = Depends(current_user),
                 db: AsyncSession = Depends(get_db)):
    owner_id = user.id
    await db.rollback()
    try:
        record = await reject_proposal(db, owner_id=owner_id, proposal_id=proposal_id, reason=payload.reason)
    except AgentProposalError as exc:
        _raise(exc)
    return await _response(db, record)


@router.post("/proposals/{proposal_id}/prepare-payment", response_model=ProposalResponse)
async def prepare_payment(proposal_id: uuid.UUID,
                          user: UserRecord = Depends(current_user),
                          registry: TrustedMerchantRegistry | None = Depends(agent_registry_dependency),
                          db: AsyncSession = Depends(get_db)):
    owner_id = user.id
    await db.rollback()
    try:
        await prepare_proposal_payment(db, owner_id=owner_id, proposal_id=proposal_id, registry=registry)
        record = await get_proposal(db, owner_id=owner_id, proposal_id=proposal_id)
        return await _response(db, record)
    except AgentProposalError as exc:
        _raise(exc)
