"""Sandbox order-creation recovery tests using the isolated PostgreSQL DB."""

import asyncio
import uuid
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.exc import DBAPIError

from test_contract_integration import app, require_test_database
from intentra.database import SessionLocal
from intentra.models.payment_attempt import PaymentAttemptRecord
from intentra.models.payment_attempt_event import PaymentAttemptEventRecord
from intentra.models.payment_checkout_approval import PaymentCheckoutApprovalRecord
from intentra.models.agent_payment_handoff import AgentPaymentHandoffRecord
from intentra.models.agent_proposal import AgentProposalEventRecord, AgentProposalRecord
from intentra.models.intent_contract import IntentContractRecord
from intentra.models.payment_reservation import PaymentReservationRecord
from intentra.routes.payments import checkout_provider
from intentra.routes.agents import agent_provider_dependency, agent_registry_dependency
from intentra.services.agent_provider import ExtractedPurchase
from intentra.services.merchant_registry import TrustedMerchantRegistry
from intentra.services.payment_execution import (
    claim_payment_execution,
    claim_payment_execution_locked,
)
from intentra.services.payment_order_binding import bind_provider_order
from intentra.services.payment_order_recovery import (
    PaymentOrderRecoveryError,
    recover_existing_paypal_order,
)
from sqlalchemy.ext.asyncio import AsyncSession
from intentra.services.paypal_sandbox import (
    PayPalOrderNotSubmittedError,
    PayPalOrderOutcomeUnknownError,
    PayPalOrderRejectedError,
    PayPalSandboxError,
    validate_paypal_order,
)
from intentra.services.payment_reservation import reserve_payment_locked


MERCHANT = "order_recovery_test_merchant"
PAYPAL_MERCHANT = "PAYPAL-ORDER-RECOVERY-MERCHANT"


class RecoveryProvider:
    def __init__(self, order_id, *, status="PAYER_ACTION_REQUIRED", merchant=PAYPAL_MERCHANT,
                 amount="1.00", currency="USD", captures=None, response_order_id=None):
        self.order_id = order_id
        self.status = status
        self.merchant = merchant
        self.amount = amount
        self.currency = currency
        self.captures = captures
        self.response_order_id = response_order_id or order_id
        self.get_calls = 0
        self.create_calls = 0
        self.capture_calls = 0

    def _order(self):
        unit = {
            "payee": {"merchant_id": self.merchant},
            "amount": {"currency_code": self.currency, "value": self.amount},
        }
        if self.captures is not None:
            unit["payments"] = {"captures": self.captures}
        return {"id": self.response_order_id, "status": self.status,
                "purchase_units": [unit],
                "links": [{"rel": "payer-action", "href": "https://www.sandbox.paypal.com/checkoutnow?token=mock"}]}

    async def get_order(self, *, order_id, expected_paypal_merchant_id, amount, currency):
        self.get_calls += 1
        order = self._order()
        validate_paypal_order(order, order_id=order_id,
                              expected_paypal_merchant_id=expected_paypal_merchant_id,
                              amount=amount, currency=currency)
        return order

    async def create_order(self, **kwargs):
        self.create_calls += 1
        raise AssertionError("Recovery/resume must not create another PayPal order.")

    async def capture_order(self, **kwargs):
        self.capture_calls += 1
        raise AssertionError("Recovery/resume must not capture the PayPal order.")


async def recovery_fixture(client, label):
    actor_id, reservation_id = await register_and_reserve(client, label)
    async with SessionLocal() as db:
        claim = await claim_payment_execution(db, reservation_id=reservation_id, actor_id=actor_id)
        reservation = await db.get(PaymentReservationRecord, reservation_id)
        return actor_id, reservation_id, claim.attempt_id, reservation.contract_id


async def run_recovery(attempt_id, reservation_id, contract_id, paypal, **changes):
    params = {
        "attempt_id": attempt_id,
        "expected_reservation_id": reservation_id,
        "expected_contract_id": contract_id,
        "expected_contract_version": 2,
        "provider_order_id": paypal.order_id,
        "dashboard_correlation_attempt_id": attempt_id,
        "expected_internal_merchant_id": MERCHANT,
        "expected_amount": Decimal("1.00"),
        "expected_currency": "USD",
        "registry": TrustedMerchantRegistry({MERCHANT: PAYPAL_MERCHANT}),
        "paypal": paypal,
    }
    params.update(changes)
    async with SessionLocal() as db:
        return await recover_existing_paypal_order(db, **params)


class RecoveryPayPal:
    def __init__(self, suffix, *, status="CREATED", approval_rel="approve"):
        self.order_id = f"ORDER-RECOVERY-{suffix}"
        self.status = status
        self.approval_rel = approval_rel
        self.create_calls = 0
        self.create_keys = []
        self.get_calls = 0
        self.capture_calls = 0
        self.create_error = None
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.block_create = False

    def _order(self, order_id=None):
        return {
            "id": order_id or self.order_id,
            "status": self.status,
            "purchase_units": [{
                "payee": {"merchant_id": PAYPAL_MERCHANT},
                "amount": {"currency_code": "USD", "value": "1.00"},
            }],
            "links": [{"rel": self.approval_rel, "href": "https://www.sandbox.paypal.com/checkoutnow?token=mock"}],
        }

    async def create_order(self, *, amount, currency, provider_idempotency_key,
                           expected_paypal_merchant_id, return_url=None, cancel_url=None):
        self.create_calls += 1
        self.create_keys.append(provider_idempotency_key)
        self.started.set()
        if self.block_create:
            await self.release.wait()
        if self.create_error is not None:
            raise self.create_error
        assert expected_paypal_merchant_id == PAYPAL_MERCHANT
        assert str(amount) == "1.00" and currency == "USD"
        return self._order()

    async def get_order(self, *, order_id, expected_paypal_merchant_id, amount, currency):
        self.get_calls += 1
        assert expected_paypal_merchant_id == PAYPAL_MERCHANT
        assert str(amount) == "1.00" and currency == "USD"
        return self._order(order_id)

    async def capture_order(self, **kwargs):
        self.capture_calls += 1
        raise AssertionError("Capture must not occur in order recovery tests.")


async def register_and_reserve(client, label):
    suffix = f"{label}-{uuid.uuid4().hex}"
    response = await client.post("/api/auth/register", json={
        "email": f"{suffix}@example.com",
        "password": "IntentraIntegrationTest2026!",
    })
    assert response.status_code == 201, response.text
    actor_id = uuid.UUID(response.json()["id"])
    contract = await client.post("/api/contracts", json={
        "merchant_id": MERCHANT, "maximum_amount": "5.00", "currency": "USD",
    })
    assert contract.status_code == 201, contract.text
    contract_id = contract.json()["id"]
    approved = await client.post(f"/api/contracts/{contract_id}/approve", json={"expected_version": 1})
    assert approved.status_code == 200, approved.text
    reservation = await client.post("/api/payments/reserve", json={
        "contract_id": contract_id, "idempotency_key": suffix,
        "merchant_id": MERCHANT, "amount": "1.00", "currency": "USD",
    })
    assert reservation.status_code == 200, reservation.text
    return actor_id, uuid.UUID(reservation.json()["reservation_id"])


class FixedAgentPurchaseProvider:
    mode = "SIMULATED"

    async def extract(self, request):
        return ExtractedPurchase(purpose="demo supplies", amount=Decimal("1.00"), currency="USD")


async def register_and_prepare_agent_attempt(client, label, *, legacy_eventless=False):
    suffix = f"{label}-{uuid.uuid4().hex}"
    registry = TrustedMerchantRegistry({MERCHANT: PAYPAL_MERCHANT})
    app.dependency_overrides[agent_provider_dependency] = lambda: FixedAgentPurchaseProvider()
    app.dependency_overrides[agent_registry_dependency] = lambda: registry
    registered = await client.post("/api/auth/register", json={
        "email": f"{suffix}@example.com", "password": "IntentraIntegrationTest2026!",
    })
    assert registered.status_code == 201, registered.text
    actor_id = uuid.UUID(registered.json()["id"])
    contract = await client.post("/api/contracts", json={
        "merchant_id": MERCHANT, "maximum_amount": "5.00", "currency": "USD",
    })
    assert contract.status_code == 201, contract.text
    contract_id = contract.json()["id"]
    approved = await client.post(f"/api/contracts/{contract_id}/approve", json={"expected_version": 1})
    assert approved.status_code == 200, approved.text
    proposal = await client.post("/api/agents/proposals", json={
        "request": "Buy demo supplies for USD 1.00", "contract_id": contract_id,
    }, headers={"Idempotency-Key": str(uuid.uuid4())})
    assert proposal.status_code == 201, proposal.text
    proposal_id = uuid.UUID(proposal.json()["proposal_id"])
    confirmed = await client.post(f"/api/agents/proposals/{proposal_id}/confirm")
    assert confirmed.status_code == 200, confirmed.text
    if not legacy_eventless:
        prepared = await client.post(f"/api/agents/proposals/{proposal_id}/prepare-payment")
        assert prepared.status_code == 200, prepared.text
        preparation = prepared.json()["payment_preparation"]
        reservation_id = uuid.UUID(preparation["reservation_id"])
        attempt_id = uuid.UUID(preparation["attempt_id"])
    else:
        # Reconstruct a pre-provenance handoff without inserting the new
        # CHECKOUT_NOT_STARTED event. This models legacy state; it deliberately
        # does not disable or mutate the append-only database trigger.
        async with SessionLocal() as db:
            async with db.begin():
                contract = await db.scalar(select(IntentContractRecord).where(
                    IntentContractRecord.id == uuid.UUID(contract_id),
                    IntentContractRecord.owner_id == actor_id,
                ).with_for_update())
                proposal_record = await db.scalar(select(AgentProposalRecord).where(
                    AgentProposalRecord.id == proposal_id,
                    AgentProposalRecord.owner_id == actor_id,
                ).with_for_update())
                reservation, _, _ = await reserve_payment_locked(
                    db,
                    contract=contract,
                    actor_id=actor_id,
                    idempotency_key=f"agent-proposal-{proposal_id}",
                    merchant_id=proposal_record.merchant_id,
                    amount=Decimal(proposal_record.proposed_amount),
                    currency=proposal_record.proposed_currency,
                    require_allow=True,
                )
                reservation = await db.scalar(select(PaymentReservationRecord).where(
                    PaymentReservationRecord.id == reservation.id,
                    PaymentReservationRecord.actor_id == actor_id,
                ).with_for_update())
                claim = await claim_payment_execution_locked(
                    db, contract=contract, reservation=reservation, actor_id=actor_id,
                )
                handoff = AgentPaymentHandoffRecord(
                    proposal_id=proposal_id,
                    owner_id=actor_id,
                    contract_id=contract.id,
                    contract_version=contract.version,
                    reservation_id=reservation.id,
                    attempt_id=claim.attempt_id,
                )
                db.add(handoff)
                db.add(AgentProposalEventRecord(
                    proposal_id=proposal_id,
                    actor_id=actor_id,
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
                reservation_id = reservation.id
                attempt_id = claim.attempt_id
    return (actor_id, uuid.UUID(contract_id), proposal_id,
            reservation_id, attempt_id)


def install_provider(paypal):
    async def provider_override():
        yield TrustedMerchantRegistry({MERCHANT: PAYPAL_MERCHANT}), paypal
    app.dependency_overrides[checkout_provider] = provider_override


@pytest.mark.asyncio
async def test_unknown_provider_order_outcome_is_durable_and_blocks_retry_and_capture():
    require_test_database()
    paypal = RecoveryPayPal(uuid.uuid4().hex)
    paypal.create_error = PayPalOrderOutcomeUnknownError("timeout after submit")
    install_provider(paypal)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:3000",
                               headers={"Origin": "http://localhost:3000"}) as owner:
            _, reservation_id = await register_and_reserve(owner, "unknown-order")
            first = await owner.post(f"/api/payments/reservations/{reservation_id}/checkout")
            assert first.status_code == 503
            assert first.headers["X-Intentra-Error-Code"] == "PROVIDER_OUTCOME_UNKNOWN"
            assert "Do not retry" in first.json()["detail"]
            retry = await owner.post(f"/api/payments/reservations/{reservation_id}/checkout")
            assert retry.status_code == 409
            assert retry.headers["X-Intentra-Error-Code"] == "PROVIDER_OUTCOME_UNKNOWN"
            async with SessionLocal() as db:
                attempt = await db.scalar(select(PaymentAttemptRecord).where(
                    PaymentAttemptRecord.reservation_id == reservation_id))
                attempt_id = attempt.id
            capture = await owner.post(f"/api/payments/attempts/{attempt_id}/capture")
            assert capture.status_code == 409
        assert paypal.create_calls == 1
        assert paypal.capture_calls == 0
        async with SessionLocal() as db:
            attempt = await db.scalar(select(PaymentAttemptRecord).where(
                PaymentAttemptRecord.reservation_id == reservation_id))
            reservation = await db.get(PaymentReservationRecord, reservation_id)
            assert attempt is not None and attempt.status == "PENDING"
            assert attempt.provider_order_id is None and attempt.capture_claimed_at is None
            assert reservation.status == "EXECUTION_PENDING"
            events = (await db.scalars(select(PaymentAttemptEventRecord).where(
                PaymentAttemptEventRecord.attempt_id == attempt.id
            ).order_by(PaymentAttemptEventRecord.created_at))).all()
            assert [event.event_type for event in events] == [
                "ORDER_CREATE_ATTEMPT_STARTED", "ORDER_CREATE_OUTCOME_UNKNOWN",
            ]
            assert all("provider_idempotency_key" not in event.event_data for event in events)
            assert await db.scalar(select(PaymentCheckoutApprovalRecord.id).where(
                PaymentCheckoutApprovalRecord.attempt_id == attempt.id)) is None
    finally:
        app.dependency_overrides.pop(checkout_provider, None)


@pytest.mark.asyncio
async def test_agent_prepared_attempt_creates_first_order_and_repeat_reuses_bound_order():
    require_test_database()
    paypal = RecoveryPayPal(uuid.uuid4().hex, status="PAYER_ACTION_REQUIRED", approval_rel="payer-action")
    install_provider(paypal)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:3000",
                               headers={"Origin": "http://localhost:3000"}) as owner:
            _, _, proposal_id, reservation_id, attempt_id = await register_and_prepare_agent_attempt(
                owner, "agent-first-order")
            first = await owner.post(f"/api/payments/reservations/{reservation_id}/checkout")
            assert first.status_code == 201, first.text
            first_payload = first.json()
            assert first_payload["provider_order_id"] == paypal.order_id
            assert first_payload["approval_url"].startswith("https://www.sandbox.paypal.com/")
            assert paypal.create_calls == 1

            second = await owner.post(f"/api/payments/reservations/{reservation_id}/checkout")
            assert second.status_code == 201, second.text
            assert second.json()["provider_order_id"] == paypal.order_id
            assert paypal.create_calls == 1
            assert len(set(paypal.create_keys)) == 1
            assert paypal.get_calls >= 1

        async with SessionLocal() as db:
            attempt = await db.get(PaymentAttemptRecord, attempt_id)
            handoff_count = await db.scalar(select(func.count(AgentPaymentHandoffRecord.id)).where(
                AgentPaymentHandoffRecord.proposal_id == proposal_id))
            reservation_count = await db.scalar(select(func.count(PaymentReservationRecord.id)).where(
                PaymentReservationRecord.id == reservation_id))
            events = (await db.scalars(select(PaymentAttemptEventRecord).where(
                PaymentAttemptEventRecord.attempt_id == attempt_id,
            ).order_by(PaymentAttemptEventRecord.created_at, PaymentAttemptEventRecord.id))).all()
            proposal_events = (await db.scalars(select(AgentProposalEventRecord).where(
                AgentProposalEventRecord.proposal_id == proposal_id,
                AgentProposalEventRecord.event_type == "PROPOSAL_PAYMENT_PREPARED",
            ))).all()
            assert attempt.provider_order_id == paypal.order_id
            assert attempt.status == "PENDING" and attempt.capture_id is None
            assert reservation_count == handoff_count == 1
            assert [event.event_type for event in events][:4] == [
                "CHECKOUT_NOT_STARTED", "ORDER_CREATE_ATTEMPT_STARTED",
                "ORDER_CREATE_PROVIDER_ACCEPTED", "ORDER_CREATE_BOUND",
            ]
            assert all("provider_idempotency_key" not in event.event_data for event in events)
            assert len(proposal_events) == 1
    finally:
        app.dependency_overrides.pop(checkout_provider, None)
        app.dependency_overrides.pop(agent_provider_dependency, None)
        app.dependency_overrides.pop(agent_registry_dependency, None)


@pytest.mark.asyncio
async def test_concurrent_first_checkout_for_agent_handoff_submits_one_order():
    require_test_database()
    paypal = RecoveryPayPal(uuid.uuid4().hex)
    paypal.block_create = True
    install_provider(paypal)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:3000",
                               headers={"Origin": "http://localhost:3000"}) as owner:
            _, _, _, reservation_id, _ = await register_and_prepare_agent_attempt(owner, "agent-concurrent")
            first_task = asyncio.create_task(owner.post(
                f"/api/payments/reservations/{reservation_id}/checkout"))
            await asyncio.wait_for(paypal.started.wait(), timeout=5)
            duplicate = await owner.post(f"/api/payments/reservations/{reservation_id}/checkout")
            assert duplicate.status_code == 409
            paypal.release.set()
            first = await first_task
            assert first.status_code == 201, first.text
        assert paypal.create_calls == 1
        assert len(set(paypal.create_keys)) == 1
    finally:
        paypal.release.set()
        app.dependency_overrides.pop(checkout_provider, None)
        app.dependency_overrides.pop(agent_provider_dependency, None)
        app.dependency_overrides.pop(agent_registry_dependency, None)


@pytest.mark.asyncio
async def test_agent_prepared_unknown_create_outcome_blocks_retry():
    require_test_database()
    paypal = RecoveryPayPal(uuid.uuid4().hex)
    paypal.create_error = PayPalOrderOutcomeUnknownError("simulated timeout after submit")
    install_provider(paypal)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:3000",
                               headers={"Origin": "http://localhost:3000"}) as owner:
            _, _, _, reservation_id, attempt_id = await register_and_prepare_agent_attempt(owner, "agent-unknown")
            first = await owner.post(f"/api/payments/reservations/{reservation_id}/checkout")
            assert first.status_code == 503
            retry = await owner.post(f"/api/payments/reservations/{reservation_id}/checkout")
            assert retry.status_code == 409
        assert paypal.create_calls == 1
        async with SessionLocal() as db:
            attempt = await db.get(PaymentAttemptRecord, attempt_id)
            events = (await db.scalars(select(PaymentAttemptEventRecord).where(
                PaymentAttemptEventRecord.attempt_id == attempt_id,
            ).order_by(PaymentAttemptEventRecord.created_at, PaymentAttemptEventRecord.id))).all()
            assert attempt.provider_order_id is None
            assert [event.event_type for event in events] == [
                "CHECKOUT_NOT_STARTED", "ORDER_CREATE_ATTEMPT_STARTED",
                "ORDER_CREATE_OUTCOME_UNKNOWN",
            ]
    finally:
        app.dependency_overrides.pop(checkout_provider, None)
        app.dependency_overrides.pop(agent_provider_dependency, None)
        app.dependency_overrides.pop(agent_registry_dependency, None)


@pytest.mark.parametrize("change", ["revoked_contract", "merchant_mismatch", "amount_mismatch"])
@pytest.mark.asyncio
async def test_agent_handoff_preflight_mismatch_never_submits_order(change):
    require_test_database()
    paypal = RecoveryPayPal(uuid.uuid4().hex)
    install_provider(paypal)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:3000",
                               headers={"Origin": "http://localhost:3000"}) as owner:
            _, contract_id, proposal_id, reservation_id, attempt_id = await register_and_prepare_agent_attempt(
                owner, f"agent-preflight-{change}")
            async with SessionLocal() as db:
                if change == "revoked_contract":
                    await db.execute(update(IntentContractRecord).where(
                        IntentContractRecord.id == contract_id).values(status="REVOKED"))
                elif change == "merchant_mismatch":
                    await db.execute(update(AgentProposalRecord).where(
                        AgentProposalRecord.id == proposal_id).values(merchant_id="different_merchant"))
                else:
                    await db.execute(update(AgentProposalRecord).where(
                        AgentProposalRecord.id == proposal_id).values(proposed_amount=Decimal("2.00")))
                await db.commit()
            response = await owner.post(f"/api/payments/reservations/{reservation_id}/checkout")
            assert response.status_code == 409
        assert paypal.create_calls == 0
        async with SessionLocal() as db:
            attempt = await db.get(PaymentAttemptRecord, attempt_id)
            events = (await db.scalars(select(PaymentAttemptEventRecord).where(
                PaymentAttemptEventRecord.attempt_id == attempt_id))).all()
            assert attempt.provider_order_id is None
            assert [event.event_type for event in events] == ["CHECKOUT_NOT_STARTED"]
    finally:
        app.dependency_overrides.pop(checkout_provider, None)
        app.dependency_overrides.pop(agent_provider_dependency, None)
        app.dependency_overrides.pop(agent_registry_dependency, None)


@pytest.mark.asyncio
async def test_definitive_provider_rejection_is_recorded_without_order_identity():
    require_test_database()
    paypal = RecoveryPayPal(uuid.uuid4().hex)
    paypal.create_error = PayPalOrderRejectedError(422)
    install_provider(paypal)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:3000",
                               headers={"Origin": "http://localhost:3000"}) as owner:
            _, reservation_id = await register_and_reserve(owner, "rejected-order")
            response = await owner.post(f"/api/payments/reservations/{reservation_id}/checkout")
            assert response.status_code == 502
            assert "rejected" in response.json()["detail"].lower()
        assert paypal.create_calls == 1
        async with SessionLocal() as db:
            attempt = await db.scalar(select(PaymentAttemptRecord).where(
                PaymentAttemptRecord.reservation_id == reservation_id))
            events = (await db.scalars(select(PaymentAttemptEventRecord).where(
                PaymentAttemptEventRecord.attempt_id == attempt.id
            ).order_by(PaymentAttemptEventRecord.created_at))).all()
            assert [event.event_type for event in events][-1] == "ORDER_CREATE_REJECTED"
            assert events[-1].event_data == {"category": "PROVIDER_REJECTED", "http_status": 422}
            assert attempt.provider_order_id is None
    finally:
        app.dependency_overrides.pop(checkout_provider, None)


@pytest.mark.asyncio
async def test_pre_submission_auth_failure_is_distinct_and_can_retry_same_attempt():
    require_test_database()
    paypal = RecoveryPayPal(uuid.uuid4().hex)
    paypal.create_error = PayPalOrderNotSubmittedError("OAuth failed before Orders POST")
    install_provider(paypal)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:3000",
                               headers={"Origin": "http://localhost:3000"}) as owner:
            _, reservation_id = await register_and_reserve(owner, "not-submitted")
            first = await owner.post(f"/api/payments/reservations/{reservation_id}/checkout")
            assert first.status_code == 503
            assert first.headers["X-Intentra-Error-Code"] == "PROVIDER_NOT_SUBMITTED"
            second = await owner.post(f"/api/payments/reservations/{reservation_id}/checkout")
            assert second.status_code == 503
            assert second.headers["X-Intentra-Error-Code"] == "PROVIDER_NOT_SUBMITTED"
        assert paypal.create_calls == 2
        assert len(set(paypal.create_keys)) == 1
        async with SessionLocal() as db:
            attempt = await db.scalar(select(PaymentAttemptRecord).where(
                PaymentAttemptRecord.reservation_id == reservation_id))
            events = (await db.scalars(select(PaymentAttemptEventRecord).where(
                PaymentAttemptEventRecord.attempt_id == attempt.id
            ).order_by(PaymentAttemptEventRecord.created_at))).all()
            assert [event.event_type for event in events] == [
                "ORDER_CREATE_ATTEMPT_STARTED", "ORDER_CREATE_NOT_SUBMITTED",
                "ORDER_CREATE_ATTEMPT_STARTED", "ORDER_CREATE_NOT_SUBMITTED",
            ]
            assert attempt.provider_order_id is None
    finally:
        app.dependency_overrides.pop(checkout_provider, None)


@pytest.mark.asyncio
async def test_provider_acceptance_survives_binding_failure_and_recovers_with_get_only(monkeypatch):
    require_test_database()
    import intentra.services.payment_orchestration as orchestration

    paypal = RecoveryPayPal(uuid.uuid4().hex)
    install_provider(paypal)
    real_bind = orchestration.bind_provider_order
    calls = 0

    async def fail_once(db, *, attempt_id, provider_order_id):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("simulated local persistence failure")
        return await real_bind(db, attempt_id=attempt_id, provider_order_id=provider_order_id)

    monkeypatch.setattr(orchestration, "bind_provider_order", fail_once)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:3000",
                               headers={"Origin": "http://localhost:3000"}) as owner:
            _, reservation_id = await register_and_reserve(owner, "bind-recovery")
            first = await owner.post(f"/api/payments/reservations/{reservation_id}/checkout")
            assert first.status_code == 409
            assert first.headers["X-Intentra-Error-Code"] == "ORDER_BINDING_RECOVERY_REQUIRED"
            recovered = await owner.post(f"/api/payments/reservations/{reservation_id}/checkout")
            assert recovered.status_code == 201, recovered.text
        assert paypal.create_calls == 1
        assert paypal.get_calls >= 2
        async with SessionLocal() as db:
            attempt = await db.scalar(select(PaymentAttemptRecord).where(
                PaymentAttemptRecord.reservation_id == reservation_id))
            events = (await db.scalars(select(PaymentAttemptEventRecord).where(
                PaymentAttemptEventRecord.attempt_id == attempt.id
            ).order_by(PaymentAttemptEventRecord.created_at))).all()
            assert attempt.provider_order_id == paypal.order_id
            accepted = next(e for e in events if e.event_type == "ORDER_CREATE_PROVIDER_ACCEPTED")
            assert accepted.event_data["provider_order_id"] == paypal.order_id
            assert "provider_idempotency_key" not in accepted.event_data
            assert "ORDER_BINDING_FAILED" in [e.event_type for e in events]
            assert "ORDER_CREATE_BOUND" in [e.event_type for e in events]
    finally:
        app.dependency_overrides.pop(checkout_provider, None)


@pytest.mark.asyncio
async def test_duplicate_checkout_during_provider_request_does_not_submit_twice():
    require_test_database()
    paypal = RecoveryPayPal(uuid.uuid4().hex)
    paypal.block_create = True
    install_provider(paypal)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:3000",
                               headers={"Origin": "http://localhost:3000"}) as owner:
            _, reservation_id = await register_and_reserve(owner, "duplicate-order")
            first_task = asyncio.create_task(owner.post(
                f"/api/payments/reservations/{reservation_id}/checkout"))
            await asyncio.wait_for(paypal.started.wait(), timeout=5)
            duplicate = await owner.post(f"/api/payments/reservations/{reservation_id}/checkout")
            assert duplicate.status_code == 409
            paypal.release.set()
            first = await first_task
            assert first.status_code == 201, first.text
        assert paypal.create_calls == 1
        assert len(set(paypal.create_keys)) == 1
    finally:
        paypal.release.set()
        app.dependency_overrides.pop(checkout_provider, None)


@pytest.mark.asyncio
async def test_legacy_attempt_without_order_event_is_held_not_replayed():
    require_test_database()
    paypal = RecoveryPayPal(uuid.uuid4().hex)
    install_provider(paypal)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:3000",
                               headers={"Origin": "http://localhost:3000"}) as owner:
            actor_id, reservation_id = await register_and_reserve(owner, "legacy-unknown")
            async with SessionLocal() as db:
                await claim_payment_execution(db, reservation_id=reservation_id, actor_id=actor_id)
            response = await owner.post(f"/api/payments/reservations/{reservation_id}/checkout")
            assert response.status_code == 409
        assert paypal.create_calls == 0
    finally:
        app.dependency_overrides.pop(checkout_provider, None)


@pytest.mark.asyncio
async def test_legacy_agent_handoff_without_preparation_provenance_is_blocked():
    require_test_database()
    paypal = RecoveryPayPal(uuid.uuid4().hex)
    install_provider(paypal)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:3000",
                               headers={"Origin": "http://localhost:3000"}) as owner:
            _, _, _, reservation_id, attempt_id = await register_and_prepare_agent_attempt(
                owner, "legacy-agent-provenance", legacy_eventless=True)
            response = await owner.post(f"/api/payments/reservations/{reservation_id}/checkout")
            assert response.status_code == 409
            assert response.headers["X-Intentra-Error-Code"] == "CHECKOUT_PROVENANCE_MISSING"
        assert paypal.create_calls == 0
        async with SessionLocal() as db:
            attempt = await db.get(PaymentAttemptRecord, attempt_id)
            reservation = await db.get(PaymentReservationRecord, reservation_id)
            events = (await db.scalars(select(PaymentAttemptEventRecord).where(
                PaymentAttemptEventRecord.attempt_id == attempt_id))).all()
            assert attempt.status == "PENDING" and attempt.provider_order_id is None
            assert reservation.status == "EXECUTION_PENDING"
            assert events == []
    finally:
        app.dependency_overrides.pop(checkout_provider, None)
        app.dependency_overrides.pop(agent_provider_dependency, None)
        app.dependency_overrides.pop(agent_registry_dependency, None)


@pytest.mark.asyncio
async def test_operator_recovery_binds_existing_order_atomically_and_is_idempotent():
    require_test_database()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:3000",
                           headers={"Origin": "http://localhost:3000"}) as owner:
        actor_id, reservation_id, attempt_id, contract_id = await recovery_fixture(owner, "recover-success")

    paypal = RecoveryProvider(f"ORDER-RECOVERY-{uuid.uuid4().hex}")
    result = await run_recovery(attempt_id, reservation_id, contract_id, paypal)
    assert result.changed is True
    assert result.provider_order_id == paypal.order_id
    repeated = await run_recovery(attempt_id, reservation_id, contract_id, paypal)
    assert repeated.changed is False
    assert paypal.get_calls == 2
    assert paypal.create_calls == paypal.capture_calls == 0

    async with SessionLocal() as db:
        attempt = await db.get(PaymentAttemptRecord, attempt_id)
        reservation = await db.get(PaymentReservationRecord, reservation_id)
        events = (await db.scalars(select(PaymentAttemptEventRecord).where(
            PaymentAttemptEventRecord.attempt_id == attempt_id,
            PaymentAttemptEventRecord.event_type == "ORDER_CREATE_RECOVERED",
        ))).all()
        assert attempt.provider_order_id == paypal.order_id
        assert attempt.status == "PENDING" and attempt.capture_claimed_at is None
        assert reservation.status == "EXECUTION_PENDING"
        assert len(events) == 1
        assert events[0].actor_id is None
        assert events[0].event_data["correlated_attempt_id"] == str(attempt_id)
        assert events[0].event_data["provider_order_id"] == paypal.order_id


@pytest.mark.asyncio
@pytest.mark.parametrize("kwargs", [
    {"response_order_id": "A-DIFFERENT-ORDER"},
    {"merchant": "ANOTHER-MERCHANT"},
    {"amount": "1.01"},
    {"currency": "CAD"},
    {"status": "COMPLETED"},
    {"captures": [{"id": "CAPTURE-ALREADY-EXISTS", "status": "COMPLETED"}]},
])
async def test_operator_recovery_rejects_unverified_or_captured_order(kwargs):
    require_test_database()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:3000",
                           headers={"Origin": "http://localhost:3000"}) as owner:
        _, reservation_id, attempt_id, contract_id = await recovery_fixture(owner, "recover-invalid")
    paypal = RecoveryProvider(f"ORDER-RECOVERY-{uuid.uuid4().hex}", **kwargs)
    with pytest.raises(PaymentOrderRecoveryError):
        await run_recovery(attempt_id, reservation_id, contract_id, paypal)
    async with SessionLocal() as db:
        attempt = await db.get(PaymentAttemptRecord, attempt_id)
        events = (await db.scalars(select(PaymentAttemptEventRecord).where(
            PaymentAttemptEventRecord.attempt_id == attempt_id,
            PaymentAttemptEventRecord.event_type == "ORDER_CREATE_RECOVERED",
        ))).all()
        assert attempt.provider_order_id is None
        assert events == []


@pytest.mark.asyncio
async def test_operator_recovery_rejects_contract_revocation_and_conflicting_binding():
    require_test_database()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:3000",
                           headers={"Origin": "http://localhost:3000"}) as owner:
        _, reservation_id, attempt_id, contract_id = await recovery_fixture(owner, "recover-revoked")
    async with SessionLocal() as db:
        contract = await db.get(__import__("intentra.models.intent_contract", fromlist=["IntentContractRecord"]).IntentContractRecord, contract_id)
        contract.status = "REVOKED"
        await db.commit()
    paypal = RecoveryProvider(f"ORDER-RECOVERY-{uuid.uuid4().hex}")
    with pytest.raises(PaymentOrderRecoveryError):
        await run_recovery(attempt_id, reservation_id, contract_id, paypal)
    assert paypal.get_calls == 1

    # A separate eligible attempt cannot be rebound to another order.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:3000",
                           headers={"Origin": "http://localhost:3000"}) as owner:
        _, reservation2, attempt2, contract2 = await recovery_fixture(owner, "recover-conflict")
    other_order = f"ORDER-BOUND-{uuid.uuid4().hex}"
    async with SessionLocal() as db:
        await bind_provider_order(db, attempt_id=attempt2, provider_order_id=other_order)
    paypal = RecoveryProvider(f"ORDER-RECOVERY-{uuid.uuid4().hex}")
    with pytest.raises(PaymentOrderRecoveryError):
        await run_recovery(attempt2, reservation2, contract2, paypal)


@pytest.mark.asyncio
async def test_operator_recovery_rejects_reservation_owned_by_another_user():
    require_test_database()
    suffix = uuid.uuid4().hex
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:3000",
                           headers={"Origin": "http://localhost:3000"}) as owner:
        _, reservation_id, attempt_id, contract_id = await recovery_fixture(owner, "recover-owner")
        outsider = await owner.post("/api/auth/register", json={
            "email": f"recovery-outsider-{suffix}@example.com",
            "password": "IntentraIntegrationTest2026!",
        })
        assert outsider.status_code == 201, outsider.text
        outsider_id = uuid.UUID(outsider.json()["id"])
    async with SessionLocal() as db:
        await db.execute(update(PaymentReservationRecord).where(
            PaymentReservationRecord.id == reservation_id,
        ).values(actor_id=outsider_id))
        await db.commit()
    paypal = RecoveryProvider(f"ORDER-RECOVERY-{uuid.uuid4().hex}")
    with pytest.raises(PaymentOrderRecoveryError):
        await run_recovery(attempt_id, reservation_id, contract_id, paypal)
    async with SessionLocal() as db:
        attempt = await db.get(PaymentAttemptRecord, attempt_id)
        assert attempt.provider_order_id is None


@pytest.mark.asyncio
async def test_concurrent_recovery_has_one_binding_and_one_immutable_event():
    require_test_database()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:3000",
                           headers={"Origin": "http://localhost:3000"}) as owner:
        _, reservation_id, attempt_id, contract_id = await recovery_fixture(owner, "recover-concurrent")
    paypal = RecoveryProvider(f"ORDER-RECOVERY-{uuid.uuid4().hex}")
    first, second = await asyncio.gather(
        run_recovery(attempt_id, reservation_id, contract_id, paypal),
        run_recovery(attempt_id, reservation_id, contract_id, paypal),
    )
    assert sorted([first.changed, second.changed]) == [False, True]
    async with SessionLocal() as db:
        events = (await db.scalars(select(PaymentAttemptEventRecord).where(
            PaymentAttemptEventRecord.attempt_id == attempt_id,
            PaymentAttemptEventRecord.event_type == "ORDER_CREATE_RECOVERED",
        ))).all()
        attempt = await db.get(PaymentAttemptRecord, attempt_id)
        assert attempt.provider_order_id == paypal.order_id
        assert len(events) == 1
        with pytest.raises(Exception):
            events[0].event_data = {"tampered": True}
            await db.commit()
        await db.rollback()


@pytest.mark.asyncio
async def test_recovery_transaction_rollback_keeps_order_unbound(monkeypatch):
    require_test_database()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:3000",
                           headers={"Origin": "http://localhost:3000"}) as owner:
        _, reservation_id, attempt_id, contract_id = await recovery_fixture(owner, "recover-rollback")
    paypal = RecoveryProvider(f"ORDER-RECOVERY-{uuid.uuid4().hex}")
    original_flush = AsyncSession.flush

    async def fail_recovery_event_flush(self, *args, **kwargs):
        if any(getattr(item, "event_type", None) == "ORDER_CREATE_RECOVERED" for item in self.new):
            raise RuntimeError("simulated audit insert failure")
        return await original_flush(self, *args, **kwargs)

    monkeypatch.setattr(AsyncSession, "flush", fail_recovery_event_flush)
    with pytest.raises(RuntimeError, match="simulated audit insert failure"):
        await run_recovery(attempt_id, reservation_id, contract_id, paypal)
    async with SessionLocal() as db:
        attempt = await db.get(PaymentAttemptRecord, attempt_id)
        events = (await db.scalars(select(PaymentAttemptEventRecord).where(
            PaymentAttemptEventRecord.attempt_id == attempt_id,
            PaymentAttemptEventRecord.event_type == "ORDER_CREATE_RECOVERED",
        ))).all()
        assert attempt.provider_order_id is None
        assert events == []


@pytest.mark.asyncio
async def test_recovered_order_resumes_approval_without_create_or_capture():
    require_test_database()
    paypal = RecoveryProvider(f"ORDER-RECOVERY-{uuid.uuid4().hex}")
    install_provider(paypal)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:3000",
                               headers={"Origin": "http://localhost:3000"}) as owner:
            _, reservation_id, attempt_id, contract_id = await recovery_fixture(owner, "recover-resume")
            recovered = await run_recovery(attempt_id, reservation_id, contract_id, paypal)
            assert recovered.changed
            handoff = await owner.post(f"/api/payments/reservations/{reservation_id}/checkout")
            assert handoff.status_code == 201, handoff.text
            payload = handoff.json()
            assert payload["provider_order_id"] == paypal.order_id
            assert "return_state" in payload
            assert paypal.create_calls == 0
            assert paypal.capture_calls == 0

            resumed = await owner.post(f"/api/payments/reservations/{reservation_id}/checkout")
            assert resumed.status_code == 201, resumed.text
            resumed_payload = resumed.json()
            assert resumed_payload["approval_id"] == payload["approval_id"]
            assert resumed_payload["provider_order_id"] == paypal.order_id
            assert resumed_payload["return_state"] != payload["return_state"]

            paypal.status = "APPROVED"
            old_state = await owner.post("/api/payments/checkout/return", json={
                "attempt_id": str(attempt_id), "state": payload["return_state"],
            })
            assert old_state.status_code == 409
            verified = await owner.post("/api/payments/checkout/return", json={
                "attempt_id": str(attempt_id), "state": resumed_payload["return_state"],
            })
            assert verified.status_code == 200, verified.text
            assert verified.json()["state"] == "APPROVED"

        async with SessionLocal() as db:
            attempt = await db.get(PaymentAttemptRecord, attempt_id)
            reservation = await db.get(PaymentReservationRecord, reservation_id)
            approval = await db.scalar(select(PaymentCheckoutApprovalRecord).where(
                PaymentCheckoutApprovalRecord.attempt_id == attempt_id))
            assert approval.state == "APPROVED"
            assert attempt.status == "PENDING" and attempt.capture_id is None
            assert reservation.status == "EXECUTION_PENDING"
        assert paypal.create_calls == 0 and paypal.capture_calls == 0
    finally:
        app.dependency_overrides.pop(checkout_provider, None)


@pytest.mark.asyncio
async def test_recovery_is_not_exposed_as_an_unauthenticated_or_owner_api():
    require_test_database()
    attempt_id = uuid.uuid4()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:3000",
                           headers={"Origin": "http://localhost:3000"}) as client:
        response = await client.post(f"/api/payments/attempts/{attempt_id}/recover-order")
    assert response.status_code == 404
