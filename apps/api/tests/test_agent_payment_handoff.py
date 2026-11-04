import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, func
from sqlalchemy.exc import DBAPIError

from test_contract_integration import app, require_test_database
from intentra.database import SessionLocal
from intentra.models.agent_payment_handoff import AgentPaymentHandoffRecord
from intentra.models.agent_proposal import AgentProposalEventRecord, AgentProposalRecord
from intentra.models.intent_contract import IntentContractRecord
from intentra.models.payment_attempt import PaymentAttemptRecord
from intentra.models.payment_attempt_event import PaymentAttemptEventRecord
from intentra.models.payment_reservation import PaymentReservationRecord
from intentra.routes.agents import agent_provider_dependency, agent_registry_dependency
from intentra.routes.payments import checkout_provider
from intentra.services.agent_provider import ExtractedPurchase
from intentra.services.merchant_registry import TrustedMerchantRegistry


class FixedProvider:
    mode = "SIMULATED"
    calls = 0

    async def extract(self, request):
        self.calls += 1
        return ExtractedPurchase(purpose="office supplies", amount=Decimal("20.00"), currency="USD")


def api_client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:3000",
                       headers={"Origin": "http://localhost:3000"})


async def setup_confirmed_proposal(*, maximum="100.00"):
    require_test_database()
    suffix = uuid.uuid4().hex
    owner, outsider = api_client(), api_client()
    provider = FixedProvider()
    provider.calls = 0
    registry = TrustedMerchantRegistry({"handoff_test_merchant": "PAYPAL-HANDOFF-TEST"})
    app.dependency_overrides[agent_provider_dependency] = lambda: provider
    app.dependency_overrides[agent_registry_dependency] = lambda: registry
    password = "IntentraHandoffTest2026!"
    for client, label in ((owner, "owner"), (outsider, "outsider")):
        registered = await client.post("/api/auth/register", json={
            "email": f"handoff-{label}-{suffix}@example.com", "password": password,
        })
        assert registered.status_code == 201, registered.text
    created = await owner.post("/api/contracts", json={
        "merchant_id": "handoff_test_merchant", "maximum_amount": maximum, "currency": "USD",
    })
    assert created.status_code == 201, created.text
    contract_id = created.json()["id"]
    approved = await owner.post(f"/api/contracts/{contract_id}/approve", json={"expected_version": 1})
    assert approved.status_code == 200, approved.text
    response = await owner.post("/api/agents/proposals", json={
        "request": "Buy office supplies for USD 20.00", "contract_id": contract_id,
    }, headers={"Idempotency-Key": str(uuid.uuid4())})
    assert response.status_code == 201, response.text
    proposal_id = response.json()["proposal_id"]
    confirmed = await owner.post(f"/api/agents/proposals/{proposal_id}/confirm")
    assert confirmed.status_code == 200, confirmed.text
    return owner, outsider, uuid.UUID(contract_id), uuid.UUID(proposal_id), provider


async def cleanup(owner, outsider):
    app.dependency_overrides.pop(agent_provider_dependency, None)
    app.dependency_overrides.pop(agent_registry_dependency, None)
    app.dependency_overrides.pop(checkout_provider, None)
    await owner.aclose()
    await outsider.aclose()


async def completed_payment_snapshot():
    async with SessionLocal() as db:
        rows = (await db.execute(select(
            PaymentAttemptRecord.id,
            PaymentAttemptRecord.status,
            PaymentAttemptRecord.provider_order_id,
            PaymentAttemptRecord.capture_id,
            PaymentReservationRecord.id,
            PaymentReservationRecord.status,
        ).join(
            PaymentReservationRecord,
            PaymentReservationRecord.id == PaymentAttemptRecord.reservation_id,
        ).where(
            PaymentAttemptRecord.status == "SUCCEEDED",
            PaymentReservationRecord.status == "CAPTURED",
        ).order_by(PaymentAttemptRecord.id))).all()
        return rows


@pytest.mark.asyncio
async def test_prepare_is_atomic_audited_and_never_calls_paypal():
    require_test_database()
    completed_before = await completed_payment_snapshot()
    owner, outsider, contract_id, proposal_id, provider = await setup_confirmed_proposal()
    checkout_calls = []
    app.dependency_overrides[checkout_provider] = lambda: checkout_calls.append("called")
    try:
        response = await owner.post(f"/api/agents/proposals/{proposal_id}/prepare-payment")
        assert response.status_code == 200, response.text
        preparation = response.json()["payment_preparation"]
        assert preparation["status"] == "EXECUTION_PENDING"
        assert response.json()["status"] == "CONFIRMED"
        assert checkout_calls == []
        assert provider.calls == 1  # Extraction only; preparation does not invoke the AI provider.
        assert (await owner.get("/api/payments/history")).json()["items"][0]["attempt_state"] == "PENDING"
        assert (await outsider.get(f"/api/agents/proposals/{proposal_id}")).status_code == 404

        async with SessionLocal() as db:
            handoff = await db.scalar(select(AgentPaymentHandoffRecord).where(
                AgentPaymentHandoffRecord.proposal_id == proposal_id))
            reservation = await db.get(PaymentReservationRecord, uuid.UUID(preparation["reservation_id"]))
            attempt = await db.get(PaymentAttemptRecord, uuid.UUID(preparation["attempt_id"]))
            event = await db.scalar(select(AgentProposalEventRecord).where(
                AgentProposalEventRecord.proposal_id == proposal_id,
                AgentProposalEventRecord.event_type == "PROPOSAL_PAYMENT_PREPARED"))
            provenance = await db.scalar(select(PaymentAttemptEventRecord).where(
                PaymentAttemptEventRecord.attempt_id == attempt.id,
                PaymentAttemptEventRecord.event_type == "CHECKOUT_NOT_STARTED"))
            assert handoff.owner_id == reservation.actor_id
            assert handoff.contract_id == contract_id == reservation.contract_id
            assert handoff.reservation_id == reservation.id == attempt.reservation_id
            assert reservation.status == "EXECUTION_PENDING"
            assert attempt.status == "PENDING" and attempt.provider_order_id is None
            assert event.event_data["attempt_id"] == str(attempt.id)
            assert event.event_data["reservation_id"] == str(reservation.id)
            assert provenance.actor_id == handoff.owner_id
            assert provenance.event_data == {
                "handoff_id": str(handoff.id),
                "proposal_id": str(proposal_id),
                "reservation_id": str(reservation.id),
                "provenance": "PAYMENT_PREPARED",
            }
            event.event_data = {"tampered": True}
            with pytest.raises(DBAPIError):
                await db.commit()
            await db.rollback()
        async with SessionLocal() as db:
            provenance = await db.scalar(select(PaymentAttemptEventRecord).where(
                PaymentAttemptEventRecord.attempt_id == uuid.UUID(preparation["attempt_id"]),
                PaymentAttemptEventRecord.event_type == "CHECKOUT_NOT_STARTED"))
            provenance.event_data = {"tampered": True}
            with pytest.raises(DBAPIError):
                await db.commit()
            await db.rollback()
        assert await completed_payment_snapshot() == completed_before
    finally:
        await cleanup(owner, outsider)


@pytest.mark.asyncio
async def test_prepare_is_idempotent_and_concurrent_requests_create_one_handoff():
    owner, outsider, _, proposal_id, _ = await setup_confirmed_proposal()
    try:
        responses = await asyncio.gather(
            owner.post(f"/api/agents/proposals/{proposal_id}/prepare-payment"),
            owner.post(f"/api/agents/proposals/{proposal_id}/prepare-payment"),
        )
        assert [response.status_code for response in responses] == [200, 200]
        payloads = [response.json()["payment_preparation"] for response in responses]
        assert payloads[0]["reservation_id"] == payloads[1]["reservation_id"]
        assert payloads[0]["attempt_id"] == payloads[1]["attempt_id"]
        async with SessionLocal() as db:
            assert await db.scalar(select(func.count(AgentPaymentHandoffRecord.id)).where(
                AgentPaymentHandoffRecord.proposal_id == proposal_id)) == 1
            assert await db.scalar(select(func.count(AgentProposalEventRecord.id)).where(
                AgentProposalEventRecord.proposal_id == proposal_id,
                AgentProposalEventRecord.event_type == "PROPOSAL_PAYMENT_PREPARED")) == 1
            assert await db.scalar(select(func.count(PaymentAttemptEventRecord.id)).where(
                PaymentAttemptEventRecord.attempt_id == uuid.UUID(payloads[0]["attempt_id"]),
                PaymentAttemptEventRecord.event_type == "CHECKOUT_NOT_STARTED")) == 1
            assert await db.scalar(select(func.count(PaymentReservationRecord.id)).where(
                PaymentReservationRecord.idempotency_key == f"agent-proposal-{proposal_id}")) == 1
    finally:
        await cleanup(owner, outsider)


@pytest.mark.asyncio
async def test_checkout_provenance_rolls_back_with_failed_handoff_audit(monkeypatch):
    require_test_database()
    owner, outsider, _, proposal_id, _ = await setup_confirmed_proposal()
    async with SessionLocal() as db:
        marker_count_before = await db.scalar(select(func.count(PaymentAttemptEventRecord.id)).where(
            PaymentAttemptEventRecord.event_type == "CHECKOUT_NOT_STARTED"))
    import intentra.services.agent_payment_handoff as handoff_service

    def fail_proposal_event(*_args, **_kwargs):
        raise RuntimeError("simulated audit construction failure")

    monkeypatch.setattr(handoff_service, "AgentProposalEventRecord", fail_proposal_event)
    try:
        async with SessionLocal() as db:
            proposal = await db.get(AgentProposalRecord, proposal_id)
            with pytest.raises(RuntimeError, match="simulated audit construction failure"):
                await handoff_service.prepare_proposal_payment(
                    db,
                    owner_id=proposal.owner_id,
                    proposal_id=proposal_id,
                    registry=TrustedMerchantRegistry({"handoff_test_merchant": "PAYPAL-HANDOFF-TEST"}),
                )
        async with SessionLocal() as db:
            assert await db.scalar(select(func.count(PaymentReservationRecord.id)).where(
                PaymentReservationRecord.idempotency_key == f"agent-proposal-{proposal_id}")) == 0
            assert await db.scalar(select(func.count(AgentPaymentHandoffRecord.id)).where(
                AgentPaymentHandoffRecord.proposal_id == proposal_id)) == 0
            assert await db.scalar(select(func.count(PaymentAttemptRecord.id)).join(
                PaymentReservationRecord,
                PaymentReservationRecord.id == PaymentAttemptRecord.reservation_id,
            ).where(PaymentReservationRecord.idempotency_key == f"agent-proposal-{proposal_id}")) == 0
            assert await db.scalar(select(func.count(PaymentAttemptEventRecord.id)).where(
                PaymentAttemptEventRecord.event_type == "CHECKOUT_NOT_STARTED")) == marker_count_before
    finally:
        await cleanup(owner, outsider)


@pytest.mark.asyncio
async def test_unconfirmed_and_other_owner_cannot_prepare():
    owner, outsider, _, proposal_id, _ = await setup_confirmed_proposal()
    try:
        async with SessionLocal() as db:
            proposal = await db.get(AgentProposalRecord, proposal_id)
            proposal.status = "READY_FOR_REVIEW"
            await db.commit()
        assert (await owner.post(f"/api/agents/proposals/{proposal_id}/prepare-payment")).status_code == 409
        assert (await outsider.post(f"/api/agents/proposals/{proposal_id}/prepare-payment")).status_code == 404
        async with SessionLocal() as db:
            assert await db.scalar(select(func.count(PaymentReservationRecord.id)).where(
                PaymentReservationRecord.idempotency_key == f"agent-proposal-{proposal_id}")) == 0
    finally:
        await cleanup(owner, outsider)


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["revoke", "version", "expired", "merchant", "currency", "amount", "budget"])
async def test_preparation_revalidates_contract_policy_and_budget(change):
    owner, outsider, contract_id, proposal_id, _ = await setup_confirmed_proposal()
    try:
        async with SessionLocal() as db:
            contract = await db.get(IntentContractRecord, contract_id)
            proposal = await db.get(AgentProposalRecord, proposal_id)
            if change == "revoke":
                contract.status = "REVOKED"
                contract.version += 1
            elif change == "version":
                contract.version += 1
            elif change == "expired":
                proposal.created_at = datetime.now(timezone.utc) - timedelta(days=2)
            elif change == "merchant":
                proposal.merchant_id = "untrusted_merchant"
            elif change == "currency":
                proposal.proposed_currency = "CAD"
            elif change == "amount":
                proposal.proposed_amount = Decimal("120.00")
            await db.commit()
        if change == "budget":
            reserve = await owner.post("/api/payments/reserve", json={
                "contract_id": str(contract_id), "idempotency_key": uuid.uuid4().hex,
                "merchant_id": "handoff_test_merchant", "amount": "90.00", "currency": "USD",
            })
            assert reserve.status_code == 200 and reserve.json()["status"] == "RESERVED"
        response = await owner.post(f"/api/agents/proposals/{proposal_id}/prepare-payment")
        assert response.status_code == 409, response.text
        async with SessionLocal() as db:
            assert await db.scalar(select(func.count(AgentPaymentHandoffRecord.id)).where(
                AgentPaymentHandoffRecord.proposal_id == proposal_id)) == 0
            assert await db.scalar(select(func.count(PaymentAttemptRecord.id)).join(
                PaymentReservationRecord,
                PaymentReservationRecord.id == PaymentAttemptRecord.reservation_id,
            ).where(PaymentReservationRecord.idempotency_key == f"agent-proposal-{proposal_id}")) == 0
    finally:
        await cleanup(owner, outsider)


@pytest.mark.asyncio
async def test_origin_protection_rejects_cross_origin_prepare():
    owner, outsider, _, proposal_id, _ = await setup_confirmed_proposal()
    try:
        response = await owner.post(f"/api/agents/proposals/{proposal_id}/prepare-payment",
                                   headers={"Origin": "https://attacker.example"})
        assert response.status_code == 403
        async with SessionLocal() as db:
            assert await db.scalar(select(func.count(AgentPaymentHandoffRecord.id)).where(
                AgentPaymentHandoffRecord.proposal_id == proposal_id)) == 0
    finally:
        await cleanup(owner, outsider)


@pytest.mark.asyncio
async def test_database_failure_rolls_back_reservation_attempt_and_handoff(monkeypatch):
    owner, outsider, _, proposal_id, _ = await setup_confirmed_proposal()
    try:
        async with SessionLocal() as db:
            event = await db.scalar(select(AgentProposalEventRecord).where(
                AgentProposalEventRecord.proposal_id == proposal_id))
            collision_id = event.correlation_id
            owner_id = uuid.UUID((await owner.get("/api/auth/me")).json()["id"])
        import intentra.services.agent_payment_handoff as handoff_service
        monkeypatch.setattr(handoff_service.uuid, "uuid4", lambda: collision_id)
        async with SessionLocal() as db:
            with pytest.raises(DBAPIError):
                await handoff_service.prepare_proposal_payment(
                    db, owner_id=owner_id, proposal_id=proposal_id,
                    registry=TrustedMerchantRegistry({"handoff_test_merchant": "PAYPAL-HANDOFF-TEST"}),
                )
        async with SessionLocal() as db:
            assert await db.scalar(select(func.count(AgentPaymentHandoffRecord.id)).where(
                AgentPaymentHandoffRecord.proposal_id == proposal_id)) == 0
            assert await db.scalar(select(func.count(PaymentReservationRecord.id)).where(
                PaymentReservationRecord.idempotency_key == f"agent-proposal-{proposal_id}")) == 0
            assert await db.scalar(select(func.count(PaymentAttemptRecord.id)).join(
                PaymentReservationRecord,
                PaymentReservationRecord.id == PaymentAttemptRecord.reservation_id,
            ).where(PaymentReservationRecord.idempotency_key == f"agent-proposal-{proposal_id}")) == 0
    finally:
        await cleanup(owner, outsider)
