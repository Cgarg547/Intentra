"""Authenticated owner-scoped operational, audit, and analytics views."""

import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import cast, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import Text

from intentra.database import get_db
from intentra.models.agent_proposal import AgentProposalEventRecord, AgentProposalRecord
from intentra.models.intent_contract import AuditEventRecord, IntentContractRecord, UserRecord
from intentra.models.payment_attempt import PaymentAttemptRecord
from intentra.models.payment_attempt_event import PaymentAttemptEventRecord
from intentra.models.payment_checkout_approval import PaymentCheckoutApprovalRecord
from intentra.models.payment_evaluation import PaymentEvaluationRecord
from intentra.models.payment_reconciliation_event import PaymentReconciliationEventRecord
from intentra.models.payment_reservation import PaymentReservationRecord
from intentra.models.session import SessionRecord
from intentra.routes.auth import current_user
from intentra.schemas.workspace import (
    AnalyticsSummary, AuditEventItem, AuditEventPage, MerchantItem,
    MerchantList, SecuritySummary, SystemStatus,
)
from intentra.services.auth import hash_session_token
from intentra.services.agent_provider import get_purchase_planning_status
from intentra.services.merchant_registry import MerchantRegistryError, load_trusted_merchant_registry

router = APIRouter(prefix="/api/workspace", tags=["Workspace"])
ACTIVE_BUDGET_STATES = ("RESERVED", "EXECUTION_PENDING", "OUTCOME_UNKNOWN", "CAPTURED")


def _safe_event_data(value, *, depth: int = 0):
    """Remove credential-like values defensively before returning audit JSON."""
    if depth > 5:
        return "[omitted]"
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            normalized = str(key).lower().replace("-", "_")
            if any(marker in normalized for marker in (
                "secret", "password", "access_token", "return_state", "idempotency_key",
                "idempotency_hash", "request_fingerprint", "cookie",
            )):
                continue
            result[str(key)[:128]] = _safe_event_data(item, depth=depth + 1)
        return result
    if isinstance(value, list):
        return [_safe_event_data(item, depth=depth + 1) for item in value[:100]]
    if isinstance(value, str):
        return value[:2000]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:2000]


@router.get("/audit", response_model=AuditEventPage)
async def audit_explorer(
    entity_type: str | None = Query(default=None, pattern="^(contract|proposal|payment|reconciliation|evaluation)$"),
    event_type: str | None = Query(default=None, min_length=1, max_length=64),
    q: str | None = Query(default=None, min_length=1, max_length=100),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10000),
    user: UserRecord = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    """Merge immutable owner-scoped events with stable chronological pagination."""
    need = {entity_type} if entity_type else {"contract", "proposal", "payment", "reconciliation", "evaluation"}
    fetch_limit = offset + limit + 1
    records: list[dict] = []

    if "contract" in need:
        rows = (await db.execute(select(AuditEventRecord, IntentContractRecord.id).join(
            IntentContractRecord, IntentContractRecord.id == AuditEventRecord.contract_id,
        ).where(IntentContractRecord.owner_id == user.id,
                *([AuditEventRecord.event_type == event_type] if event_type else []),
                *([cast(AuditEventRecord.event_data, Text).ilike(f"%{q}%")] if q else []))
            .order_by(AuditEventRecord.created_at.desc(), AuditEventRecord.id.desc()).limit(fetch_limit))).all()
        for event, contract_id in rows:
            records.append(dict(event_id=event.id, correlation_id=None, entity_type="contract", entity_id=contract_id,
                related_ids={"contract_id": contract_id}, actor_id=event.actor_id, event_type=event.event_type,
                event_data=event.event_data, created_at=event.created_at))

    if "proposal" in need:
        rows = (await db.execute(select(AgentProposalEventRecord, AgentProposalRecord).join(
            AgentProposalRecord, AgentProposalRecord.id == AgentProposalEventRecord.proposal_id,
        ).where(AgentProposalRecord.owner_id == user.id,
                *([AgentProposalEventRecord.event_type == event_type] if event_type else []),
                *([cast(AgentProposalEventRecord.event_data, Text).ilike(f"%{q}%")] if q else []))
            .order_by(AgentProposalEventRecord.created_at.desc(), AgentProposalEventRecord.id.desc()).limit(fetch_limit))).all()
        for event, proposal in rows:
            links = {"proposal_id": proposal.id}
            if proposal.contract_id:
                links["contract_id"] = proposal.contract_id
            records.append(dict(event_id=event.id, correlation_id=event.correlation_id, entity_type="proposal",
                entity_id=proposal.id, related_ids=links, actor_id=event.actor_id, event_type=event.event_type,
                event_data=event.event_data, created_at=event.created_at))

    if "payment" in need:
        rows = (await db.execute(select(PaymentAttemptEventRecord, PaymentAttemptRecord, PaymentReservationRecord)
            .join(PaymentAttemptRecord, PaymentAttemptRecord.id == PaymentAttemptEventRecord.attempt_id)
            .join(PaymentReservationRecord, PaymentReservationRecord.id == PaymentAttemptRecord.reservation_id)
            .where(PaymentReservationRecord.actor_id == user.id,
                *([PaymentAttemptEventRecord.event_type == event_type] if event_type else []),
                *([cast(PaymentAttemptEventRecord.event_data, Text).ilike(f"%{q}%")] if q else []))
            .order_by(PaymentAttemptEventRecord.created_at.desc(), PaymentAttemptEventRecord.id.desc()).limit(fetch_limit))).all()
        for event, attempt, reservation in rows:
            records.append(dict(event_id=event.id, correlation_id=event.event_correlation_id, entity_type="payment",
                entity_id=attempt.id, related_ids={"attempt_id": attempt.id, "reservation_id": reservation.id,
                    "contract_id": reservation.contract_id}, actor_id=event.actor_id, event_type=event.event_type,
                event_data=event.event_data, created_at=event.created_at))

    if "reconciliation" in need:
        rows = (await db.execute(select(PaymentReconciliationEventRecord, PaymentReservationRecord).join(
            PaymentAttemptRecord, PaymentAttemptRecord.id == PaymentReconciliationEventRecord.attempt_id,
        ).join(PaymentReservationRecord, PaymentReservationRecord.id == PaymentAttemptRecord.reservation_id)
            .where(PaymentReservationRecord.actor_id == user.id,
                *([PaymentReconciliationEventRecord.event_type == event_type] if event_type else []),
                *([cast(PaymentReconciliationEventRecord.evidence_data, Text).ilike(f"%{q}%")] if q else []))
            .order_by(PaymentReconciliationEventRecord.created_at.desc(), PaymentReconciliationEventRecord.id.desc()).limit(fetch_limit))).all()
        for event, reservation in rows:
            records.append(dict(event_id=event.id, correlation_id=event.operation_id, entity_type="reconciliation",
                entity_id=event.attempt_id, related_ids={"attempt_id": event.attempt_id,
                    "reservation_id": reservation.id, "contract_id": reservation.contract_id}, actor_id=None,
                event_type=event.event_type, event_data=event.evidence_data, created_at=event.created_at))

    if "evaluation" in need and (event_type is None or event_type.startswith("PAYMENT_EVALUATED:")):
        rows = (await db.execute(select(PaymentEvaluationRecord, IntentContractRecord).join(
            IntentContractRecord, IntentContractRecord.id == PaymentEvaluationRecord.contract_id,
        ).where(IntentContractRecord.owner_id == user.id, PaymentEvaluationRecord.actor_id == user.id,
            *([PaymentEvaluationRecord.decision == event_type.removeprefix("PAYMENT_EVALUATED:")] if event_type and event_type.startswith("PAYMENT_EVALUATED:") else []),
            *([cast(PaymentEvaluationRecord.reason, Text).ilike(f"%{q}%")] if q else []))
            .order_by(PaymentEvaluationRecord.created_at.desc(), PaymentEvaluationRecord.id.desc()).limit(fetch_limit))).all()
        for evaluation, contract in rows:
            records.append(dict(event_id=evaluation.id, correlation_id=None, entity_type="evaluation",
                entity_id=evaluation.id, related_ids={"contract_id": contract.id}, actor_id=evaluation.actor_id,
                event_type=f"PAYMENT_EVALUATED:{evaluation.decision}", event_data={
                    "decision": evaluation.decision, "reason": evaluation.reason,
                    "merchant_id": evaluation.merchant_id, "amount": str(evaluation.amount),
                    "currency": evaluation.currency, "contract_version": evaluation.contract_version,
                }, created_at=evaluation.created_at))

    # A literal event_type filter for synthetic evaluation records is handled in
    # Python because those records do not persist an event_type column.
    if event_type and event_type.startswith("PAYMENT_EVALUATED:"):
        records = [r for r in records if r["entity_type"] != "evaluation" or r["event_type"] == event_type]
    records.sort(key=lambda item: (item["created_at"], str(item["event_id"])), reverse=True)
    page = records[offset:offset + limit + 1]
    has_more = len(page) > limit
    page = page[:limit]
    actor_ids = {row["actor_id"] for row in page if row["actor_id"] is not None}
    actor_emails = {}
    if actor_ids:
        actor_emails = dict((await db.execute(select(UserRecord.id, UserRecord.email).where(
            UserRecord.id.in_(actor_ids)))).all())
    items = [AuditEventItem(**{
        **row, "actor_email": actor_emails.get(row["actor_id"]),
        "event_data": _safe_event_data(row["event_data"]),
    }) for row in page]
    return AuditEventPage(items=items, limit=limit, offset=offset,
        next_offset=offset + limit if has_more else None)


@router.get("/merchants", response_model=MerchantList)
async def merchant_registry(user: UserRecord = Depends(current_user)):
    del user
    try:
        registry = load_trusted_merchant_registry()
    except MerchantRegistryError:
        raise HTTPException(status_code=503, detail="Trusted merchant registry is unavailable.") from None
    if registry is None:
        return MerchantList(items=[], configured=False)
    items = [MerchantItem(internal_merchant_id=merchant.internal_merchant_id,
        paypal_merchant_id=merchant.paypal_merchant_id) for merchant in registry.verified_mappings()]
    return MerchantList(items=items, configured=True)


@router.get("/security", response_model=SecuritySummary)
async def security_summary(
    request: Request,
    user: UserRecord = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    from intentra.routes.auth import COOKIE_NAME
    from intentra.services.merchant_registry import load_trusted_merchant_registry
    raw_cookie = request.cookies.get(COOKIE_NAME)
    current_hash = hash_session_token(raw_cookie) if raw_cookie else None
    now = datetime.now(timezone.utc)
    active = select(SessionRecord).where(SessionRecord.user_id == user.id,
        SessionRecord.revoked_at.is_(None), SessionRecord.expires_at > now)
    active_count = await db.scalar(select(func.count()).select_from(active.subquery())) or 0
    current_valid = bool(current_hash and await db.scalar(select(SessionRecord.id).where(
        SessionRecord.user_id == user.id, SessionRecord.token_hash == current_hash,
        SessionRecord.revoked_at.is_(None), SessionRecord.expires_at > now)))
    contract_states = dict((await db.execute(select(IntentContractRecord.status, func.count())
        .where(IntentContractRecord.owner_id == user.id).group_by(IntentContractRecord.status))).all())
    payment_states = dict((await db.execute(select(PaymentAttemptRecord.status, func.count())
        .join(PaymentReservationRecord, PaymentReservationRecord.id == PaymentAttemptRecord.reservation_id)
        .where(PaymentReservationRecord.actor_id == user.id).group_by(PaymentAttemptRecord.status))).all())
    decisions = dict((await db.execute(select(PaymentEvaluationRecord.decision, func.count())
        .where(PaymentEvaluationRecord.actor_id == user.id).group_by(PaymentEvaluationRecord.decision))).all())
    try:
        registry = load_trusted_merchant_registry()
        merchant_count = len(registry.verified_mappings()) if registry else 0
    except MerchantRegistryError:
        merchant_count = 0
    return SecuritySummary(authenticated=True, active_session_count=active_count,
        current_session_valid=current_valid, contracts={k: int(v) for k, v in contract_states.items()},
        trusted_merchant_count=merchant_count, payment_states={k: int(v) for k, v in payment_states.items()},
        policy_decisions={k: int(v) for k, v in decisions.items()},
        unresolved_attempts=int(payment_states.get("UNKNOWN", 0)), generated_at=now)


@router.get("/analytics", response_model=AnalyticsSummary)
async def analytics_summary(user: UserRecord = Depends(current_user), db: AsyncSession = Depends(get_db)):
    payment_rows = (await db.execute(select(PaymentAttemptRecord.status, PaymentReservationRecord.currency,
        func.count(PaymentAttemptRecord.id),
        func.coalesce(func.sum(PaymentReservationRecord.amount), 0))
        .join(PaymentReservationRecord, PaymentReservationRecord.id == PaymentAttemptRecord.reservation_id)
        .where(PaymentReservationRecord.actor_id == user.id)
        .group_by(PaymentAttemptRecord.status, PaymentReservationRecord.currency))).all()
    states = [{"state": state, "currency": currency, "count": int(count), "amount": amount}
        for state, currency, count, amount in payment_rows]
    total_count = sum(row["count"] for row in states)
    unknown_count = sum(row["count"] for row in states if row["state"] == "UNKNOWN")
    successful_count = sum(row["count"] for row in states if row["state"] == "SUCCEEDED")

    contracts = (await db.scalars(select(IntentContractRecord).where(IntentContractRecord.owner_id == user.id))).all()
    reservations = (await db.scalars(select(PaymentReservationRecord).where(
        PaymentReservationRecord.actor_id == user.id))).all()
    spent_by_contract: dict[uuid.UUID, Decimal] = {}
    for reservation in reservations:
        if reservation.status in ACTIVE_BUDGET_STATES:
            spent_by_contract[reservation.contract_id] = spent_by_contract.get(reservation.contract_id, Decimal("0")) + reservation.amount
    budget = [{"contract_id": contract.id, "merchant_id": contract.merchant_id,
        "maximum_amount": contract.maximum_amount, "currency": contract.currency,
        "consumed_amount": spent_by_contract.get(contract.id, Decimal("0")),
        "remaining_amount": max(Decimal("0"), contract.maximum_amount - spent_by_contract.get(contract.id, Decimal("0"))),
        "status": contract.status} for contract in contracts]

    captured_rows = (await db.execute(select(PaymentReservationRecord.merchant_id,
        PaymentReservationRecord.currency, func.sum(PaymentReservationRecord.amount),
        func.count(PaymentReservationRecord.id)).where(PaymentReservationRecord.actor_id == user.id,
        PaymentReservationRecord.status == "CAPTURED").group_by(
            PaymentReservationRecord.merchant_id, PaymentReservationRecord.currency))).all()
    captured_by_merchant = [{"merchant_id": merchant, "currency": currency, "amount": amount, "count": int(count)}
        for merchant, currency, amount, count in captured_rows]
    decisions = dict((await db.execute(select(PaymentEvaluationRecord.decision, func.count())
        .where(PaymentEvaluationRecord.actor_id == user.id).group_by(PaymentEvaluationRecord.decision))).all())
    proposal_states = dict((await db.execute(select(AgentProposalRecord.status, func.count())
        .where(AgentProposalRecord.owner_id == user.id).group_by(AgentProposalRecord.status))).all())
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    daily_rows = (await db.execute(select(func.date(PaymentAttemptEventRecord.created_at),
        PaymentReservationRecord.currency,
        func.sum(PaymentReservationRecord.amount), func.count(func.distinct(PaymentReservationRecord.id)))
        .join(PaymentAttemptRecord, PaymentAttemptRecord.id == PaymentAttemptEventRecord.attempt_id)
        .join(PaymentReservationRecord, PaymentReservationRecord.id == PaymentAttemptRecord.reservation_id)
        .where(PaymentReservationRecord.actor_id == user.id,
            PaymentAttemptEventRecord.event_type == "CAPTURE_COMPLETED",
            PaymentAttemptEventRecord.created_at >= cutoff)
        .group_by(func.date(PaymentAttemptEventRecord.created_at), PaymentReservationRecord.currency)
        .order_by(func.date(PaymentAttemptEventRecord.created_at)))).all()
    daily = [{"date": str(day), "currency": code, "amount": amount, "count": int(count)}
        for day, code, amount, count in daily_rows]
    recent_rows = (await db.execute(select(PaymentAttemptRecord, PaymentReservationRecord, PaymentCheckoutApprovalRecord.state)
        .join(PaymentReservationRecord, PaymentReservationRecord.id == PaymentAttemptRecord.reservation_id)
        .outerjoin(PaymentCheckoutApprovalRecord, PaymentCheckoutApprovalRecord.attempt_id == PaymentAttemptRecord.id)
        .where(PaymentReservationRecord.actor_id == user.id)
        .order_by(PaymentAttemptRecord.created_at.desc(), PaymentAttemptRecord.id.desc()).limit(100))).all()
    transactions = [{"attempt_id": attempt.id, "reservation_id": reservation.id,
        "contract_id": reservation.contract_id, "merchant_id": reservation.merchant_id,
        "amount": reservation.amount, "currency": reservation.currency,
        "state": attempt.status, "reservation_state": reservation.status,
        "approval_state": approval_state, "created_at": attempt.created_at}
        for attempt, reservation, approval_state in recent_rows
    ]
    return AnalyticsSummary(payments={"count": total_count, "successful_count": successful_count,
        "unknown_count": unknown_count}, payment_states=states, budget_by_contract=budget,
        captured_by_merchant=captured_by_merchant, policy_decisions={k: int(v) for k, v in decisions.items()},
        proposals={k: int(v) for k, v in proposal_states.items()}, daily_captured=daily,
        transactions=transactions)


@router.get("/status", response_model=SystemStatus)
async def system_status(user: UserRecord = Depends(current_user), db: AsyncSession = Depends(get_db)):
    del user
    try:
        await db.execute(text("SELECT 1"))
        database = "available"
    except Exception:
        await db.rollback()
        database = "unavailable"
    registry_state = "unconfigured"
    paypal_state = "unconfigured"
    try:
        registry = load_trusted_merchant_registry()
        registry_state = "configured" if registry and registry.verified_mappings() else "unconfigured"
    except MerchantRegistryError:
        registry_state = "invalid"
    if os.getenv("PAYPAL_SANDBOX_CLIENT_ID") and os.getenv("PAYPAL_SANDBOX_CLIENT_SECRET"):
        paypal_state = "credentials_configured"
    llm_status = await get_purchase_planning_status()
    return SystemStatus(api="available", database=database, paypal_sandbox=paypal_state,
        trusted_merchants=registry_state, llm_mode=llm_status["configuration"],
        llm_provider=llm_status["provider"], llm_runtime=llm_status["runtime"],
        llm_model_status=llm_status["model"],
        checked_at=datetime.now(timezone.utc))
