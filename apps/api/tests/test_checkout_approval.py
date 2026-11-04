import asyncio
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update

from test_contract_integration import app, require_test_database
from test_payment_order_binding import create_claimed_attempt
from intentra.database import SessionLocal
from intentra.models.intent_contract import IntentContractRecord
from intentra.models.payment_attempt import PaymentAttemptRecord
from intentra.models.payment_attempt_event import PaymentAttemptEventRecord
from intentra.models.payment_checkout_approval import PaymentCheckoutApprovalRecord
from intentra.models.payment_reservation import PaymentReservationRecord
from intentra.routes.payments import checkout_provider
from intentra.services.checkout_approval import (
    CheckoutApprovalError, initiate_checkout_approval, verify_checkout_return,
)
from intentra.services.merchant_registry import TrustedMerchantRegistry
from intentra.services.payment_execution import claim_payment_execution
from intentra.services.payment_order_binding import bind_provider_order
from intentra.services.paypal_sandbox import PayPalSandboxError


class FakePayPal:
    def __init__(self, payload=None, error=None, gate=None):
        self.payload = payload or {"id": "MOCK-ORDER", "status": "CREATED", "purchase_units": [{"payee": {"merchant_id": "PAYPAL-MERCHANT"}, "amount": {"currency_code": "USD", "value": "40.00"}}]}
        self.error = error
        self.gate = gate
        self.calls = 0

    async def get_order(self, *, order_id, expected_paypal_merchant_id, amount, currency):
        self.calls += 1
        if self.gate:
            await self.gate.wait()
        if self.error:
            raise self.error
        if order_id != self.payload.get("id"):
            raise PayPalSandboxError("PayPal order ID mismatch")
        try:
            units = self.payload["purchase_units"]
            if not isinstance(units, list) or len(units) != 1 or not isinstance(units[0], dict):
                raise ValueError
            unit = units[0]
            payee, provider_amount = unit["payee"], unit["amount"]
            if not isinstance(payee, dict) or not isinstance(provider_amount, dict):
                raise ValueError
            if payee["merchant_id"] != expected_paypal_merchant_id:
                raise PayPalSandboxError("PayPal order merchant mismatch")
            if provider_amount["currency_code"] != currency or Decimal(provider_amount["value"]) != amount:
                raise PayPalSandboxError("PayPal order amount mismatch")
        except (KeyError, TypeError, IndexError, ValueError) as exc:
            raise PayPalSandboxError("Invalid PayPal order response") from exc
        return self.payload


def registry():
    return TrustedMerchantRegistry({"binding_test_merchant": "PAYPAL-MERCHANT"})


async def owned_attempt():
    require_test_database()
    attempt_id = await create_claimed_attempt()
    order_id = "MOCK-ORDER-" + uuid.uuid4().hex
    async with SessionLocal() as db:
        await bind_provider_order(db, attempt_id=attempt_id, provider_order_id=order_id)
        attempt = await db.get(PaymentAttemptRecord, attempt_id)
        reservation = await db.get(PaymentReservationRecord, attempt.reservation_id)
        actor_id = reservation.actor_id
    return attempt_id, actor_id, order_id


async def launch(attempt_id, actor_id, paypal=None, lifetime=None):
    async with SessionLocal() as db:
        args = dict(db=db, attempt_id=attempt_id, actor_id=actor_id,
                    registry=registry(), paypal=paypal or FakePayPal())
        if lifetime is not None:
            args["lifetime"] = lifetime
        return await initiate_checkout_approval(**args)


@pytest.mark.asyncio
async def test_checkout_creation_persists_hash_and_event_without_raw_token():
    attempt_id, actor, order_id = await owned_attempt()
    paypal = FakePayPal({"id": order_id, "status": "CREATED", "purchase_units": [{"payee": {"merchant_id": "PAYPAL-MERCHANT"}, "amount": {"currency_code": "USD", "value": "40.00"}}]})
    handoff = await launch(attempt_id, actor, paypal)
    async with SessionLocal() as db:
        approval = await db.scalar(select(PaymentCheckoutApprovalRecord).where(PaymentCheckoutApprovalRecord.id == handoff.approval_id))
        events = (await db.scalars(select(PaymentAttemptEventRecord).where(PaymentAttemptEventRecord.attempt_id == attempt_id))).all()
    assert approval.state == "PENDING"
    assert approval.return_state_hash != handoff.return_state
    assert handoff.return_state not in str(approval.return_state_hash)
    assert any(e.event_type == "CHECKOUT_CREATED" for e in events)


@pytest.mark.asyncio
async def test_resuming_pending_handoff_rotates_single_use_state_for_same_order():
    attempt_id, actor, order_id = await owned_attempt()
    paypal = FakePayPal({"id": order_id, "status": "PAYER_ACTION_REQUIRED", "purchase_units": [{
        "payee": {"merchant_id": "PAYPAL-MERCHANT"},
        "amount": {"currency_code": "USD", "value": "40.00"},
    }]})
    first = await launch(attempt_id, actor, paypal)
    second = await launch(attempt_id, actor, paypal)
    assert second.approval_id == first.approval_id
    assert second.provider_order_id == order_id
    assert second.return_state != first.return_state
    async with SessionLocal() as db:
        approval = await db.get(PaymentCheckoutApprovalRecord, first.approval_id)
        events = (await db.scalars(select(PaymentAttemptEventRecord).where(
            PaymentAttemptEventRecord.attempt_id == attempt_id,
        ))).all()
    assert approval.return_state_hash == hashlib.sha256(second.return_state.encode()).hexdigest()
    assert sum(event.event_type == "CHECKOUT_CREATED" for event in events) == 1
    assert sum(event.event_type == "CHECKOUT_HANDOFF_RESUMED" for event in events) == 1
    paypal.payload = {**paypal.payload, "status": "APPROVED"}
    async with SessionLocal() as db:
        with pytest.raises(CheckoutApprovalError):
            await verify_checkout_return(db, attempt_id=attempt_id, actor_id=actor,
                return_state=first.return_state, registry=registry(), paypal=paypal)
    async with SessionLocal() as db:
        verified = await verify_checkout_return(db, attempt_id=attempt_id, actor_id=actor,
            return_state=second.return_state, registry=registry(), paypal=paypal)
    assert verified.state == "APPROVED"


@pytest.mark.asyncio
async def test_verified_return_persists_approval_and_does_not_capture():
    attempt_id, actor, order_id = await owned_attempt()
    p = FakePayPal({"id": order_id, "status": "CREATED", "purchase_units": [{"payee": {"merchant_id": "PAYPAL-MERCHANT"}, "amount": {"currency_code": "USD", "value": "40.00"}}]})
    handoff = await launch(attempt_id, actor, p)
    p.payload = {**p.payload, "status": "APPROVED"}
    async with SessionLocal() as db:
        result = await verify_checkout_return(db, attempt_id=attempt_id, actor_id=actor, return_state=handoff.return_state, registry=registry(), paypal=p)
    assert result.state == "APPROVED"
    async with SessionLocal() as db:
        approval = await db.get(PaymentCheckoutApprovalRecord, handoff.approval_id)
        attempt = await db.get(PaymentAttemptRecord, attempt_id)
        reservation = await db.get(PaymentReservationRecord, (await db.get(PaymentAttemptRecord, attempt_id)).reservation_id)
        events = (await db.scalars(select(PaymentAttemptEventRecord).where(PaymentAttemptEventRecord.attempt_id == attempt_id))).all()
    assert approval.verified_provider_status == "APPROVED"
    assert approval.verified_merchant_id == "PAYPAL-MERCHANT"
    assert approval.verified_amount == Decimal("40.00")
    assert approval.verified_currency == "USD"
    assert approval.verified_at and approval.consumed_at
    assert attempt.status == "PENDING" and reservation.status == "EXECUTION_PENDING"
    assert any(e.event_type == "CHECKOUT_APPROVED" for e in events)
    assert not hasattr(p, "capture_order")

    # The event rows are protected by the database append-only trigger.
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError
    async with SessionLocal() as db:
        with pytest.raises(DBAPIError):
            await db.execute(text("UPDATE payment_attempt_events SET event_type = 'ALTERED' WHERE attempt_id = :attempt_id"), {"attempt_id": attempt_id})
        await db.rollback()


@pytest.mark.asyncio
async def test_invalid_token_wrong_owner_and_replay_rejected():
    attempt_id, actor, order_id = await owned_attempt()
    p = FakePayPal({"id": order_id, "status": "CREATED", "purchase_units": [{"payee": {"merchant_id": "PAYPAL-MERCHANT"}, "amount": {"currency_code": "USD", "value": "40.00"}}]})
    h = await launch(attempt_id, actor, p)
    async with SessionLocal() as db:
        with pytest.raises(CheckoutApprovalError):
            await verify_checkout_return(db, attempt_id=attempt_id, actor_id=uuid.uuid4(), return_state=h.return_state, registry=registry(), paypal=p)
    async with SessionLocal() as db:
        with pytest.raises(CheckoutApprovalError):
            await verify_checkout_return(db, attempt_id=attempt_id, actor_id=actor, return_state="x" * 48, registry=registry(), paypal=p)
    p.payload = {**p.payload, "status": "APPROVED"}
    async with SessionLocal() as db:
        await verify_checkout_return(db, attempt_id=attempt_id, actor_id=actor, return_state=h.return_state, registry=registry(), paypal=p)
    async with SessionLocal() as db:
        with pytest.raises(CheckoutApprovalError):
            await verify_checkout_return(db, attempt_id=attempt_id, actor_id=actor, return_state=h.return_state, registry=registry(), paypal=p)


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["status", "merchant", "amount", "currency", "order", "timeout", "malformed"])
async def test_unverified_provider_result_never_approves(case):
    attempt_id, actor, order_id = await owned_attempt()
    p = FakePayPal({"id": order_id, "status": "CREATED", "purchase_units": [{"payee": {"merchant_id": "PAYPAL-MERCHANT"}, "amount": {"currency_code": "USD", "value": "40.00"}}]})
    h = await launch(attempt_id, actor, p)
    if case == "status": p.payload["status"] = "CREATED"
    elif case == "merchant": p.payload["purchase_units"][0]["payee"]["merchant_id"] = "OTHER"
    elif case == "amount": p.payload["purchase_units"][0]["amount"]["value"] = "41.00"
    elif case == "currency": p.payload["purchase_units"][0]["amount"]["currency_code"] = "CAD"
    elif case == "order": p.payload["id"] = "OTHER-ORDER"
    elif case == "malformed": p.payload["purchase_units"] = []
    elif case == "timeout": p.error = PayPalSandboxError("timeout")
    async with SessionLocal() as db:
        with pytest.raises(CheckoutApprovalError):
            await verify_checkout_return(db, attempt_id=attempt_id, actor_id=actor, return_state=h.return_state, registry=registry(), paypal=p)
    async with SessionLocal() as db:
        approval = await db.get(PaymentCheckoutApprovalRecord, h.approval_id)
    assert approval.state == "PENDING"


@pytest.mark.asyncio
async def test_expiry_and_concurrent_returns_have_one_consumer():
    attempt_id, actor, order_id = await owned_attempt()
    p = FakePayPal({"id": order_id, "status": "CREATED", "purchase_units": [{"payee": {"merchant_id": "PAYPAL-MERCHANT"}, "amount": {"currency_code": "USD", "value": "40.00"}}]})
    h = await launch(attempt_id, actor, p, timedelta(seconds=0.01))
    await asyncio.sleep(0.03)
    async with SessionLocal() as db:
        res = await verify_checkout_return(db, attempt_id=attempt_id, actor_id=actor, return_state=h.return_state, registry=registry(), paypal=p)
    assert res.state == "EXPIRED"

    attempt2, actor2, order2 = await owned_attempt()
    p2 = FakePayPal({"id": order2, "status": "CREATED", "purchase_units": [{"payee": {"merchant_id": "PAYPAL-MERCHANT"}, "amount": {"currency_code": "USD", "value": "40.00"}}]})
    h2 = await launch(attempt2, actor2, p2)
    p2.payload["status"] = "APPROVED"
    gate = asyncio.Event(); p2.gate = gate
    async def consume():
        async with SessionLocal() as db:
            try:
                return await verify_checkout_return(db, attempt_id=attempt2, actor_id=actor2, return_state=h2.return_state, registry=registry(), paypal=p2)
            except CheckoutApprovalError:
                return None
    a = asyncio.create_task(consume()); b = asyncio.create_task(consume())
    while p2.calls < 2: await asyncio.sleep(0)
    gate.set()
    results = await asyncio.gather(a, b)
    assert sum(x is not None for x in results) == 1


@pytest.mark.asyncio
async def test_revocation_or_state_change_during_provider_lookup_blocks_approval():
    attempt_id, actor, order_id = await owned_attempt()
    p = FakePayPal({"id": order_id, "status": "CREATED", "purchase_units": [{"payee": {"merchant_id": "PAYPAL-MERCHANT"}, "amount": {"currency_code": "USD", "value": "40.00"}}]})
    h = await launch(attempt_id, actor, p)
    p.payload["status"] = "APPROVED"
    gate = asyncio.Event(); p.gate = gate
    async def consume():
        async with SessionLocal() as db:
            try: return await verify_checkout_return(db, attempt_id=attempt_id, actor_id=actor, return_state=h.return_state, registry=registry(), paypal=p)
            except CheckoutApprovalError: return None
    task = asyncio.create_task(consume())
    while p.calls < 1: await asyncio.sleep(0)
    async with SessionLocal() as db:
        attempt = await db.get(PaymentAttemptRecord, attempt_id)
        reservation = await db.get(PaymentReservationRecord, attempt.reservation_id)
        await db.execute(update(IntentContractRecord).where(IntentContractRecord.id == reservation.contract_id).values(status="REVOKED", version=IntentContractRecord.version + 1))
        await db.commit()
    gate.set()
    assert await task is None
    async with SessionLocal() as db:
        approval = await db.get(PaymentCheckoutApprovalRecord, h.approval_id)
    assert approval.state == "PENDING"


@pytest.mark.asyncio
async def test_reservation_change_during_provider_lookup_blocks_approval():
    attempt_id, actor, order_id = await owned_attempt()
    p = FakePayPal({"id": order_id, "status": "CREATED", "purchase_units": [{"payee": {"merchant_id": "PAYPAL-MERCHANT"}, "amount": {"currency_code": "USD", "value": "40.00"}}]})
    h = await launch(attempt_id, actor, p)
    p.payload["status"] = "APPROVED"
    gate = asyncio.Event(); p.gate = gate

    async def consume():
        async with SessionLocal() as db:
            try:
                return await verify_checkout_return(db, attempt_id=attempt_id, actor_id=actor,
                    return_state=h.return_state, registry=registry(), paypal=p)
            except CheckoutApprovalError:
                return None

    task = asyncio.create_task(consume())
    while p.calls < 1: await asyncio.sleep(0)
    async with SessionLocal() as db:
        attempt = await db.get(PaymentAttemptRecord, attempt_id)
        await db.execute(update(PaymentReservationRecord).where(
            PaymentReservationRecord.id == attempt.reservation_id,
        ).values(status="CANCELLED"))
        await db.commit()
    gate.set()
    assert await task is None
    async with SessionLocal() as db:
        approval = await db.get(PaymentCheckoutApprovalRecord, h.approval_id)
    assert approval.state == "PENDING"


@pytest.mark.asyncio
async def test_database_rollback_does_not_leave_approval_or_event(monkeypatch):
    attempt_id, actor, order_id = await owned_attempt()
    p = FakePayPal({"id": order_id, "status": "CREATED", "purchase_units": [{"payee": {"merchant_id": "PAYPAL-MERCHANT"}, "amount": {"currency_code": "USD", "value": "40.00"}}]})
    h = await launch(attempt_id, actor, p)
    p.payload["status"] = "APPROVED"
    import intentra.services.checkout_approval as service
    original = service._event

    def invalid_event(db, attempt_id, actor_id, event_type, correlation_id, data=None):
        if event_type == "CHECKOUT_APPROVED":
            raise RuntimeError("simulated persistence failure")
        return original(db, attempt_id, actor_id, event_type, correlation_id, data)

    monkeypatch.setattr(service, "_event", invalid_event)
    async with SessionLocal() as db:
        with pytest.raises(RuntimeError, match="simulated persistence failure"):
            await verify_checkout_return(db, attempt_id=attempt_id, actor_id=actor,
                return_state=h.return_state, registry=registry(), paypal=p)
    async with SessionLocal() as db:
        approval = await db.get(PaymentCheckoutApprovalRecord, h.approval_id)
        events = (await db.scalars(select(PaymentAttemptEventRecord).where(
            PaymentAttemptEventRecord.attempt_id == attempt_id,
            PaymentAttemptEventRecord.event_type == "CHECKOUT_APPROVED",
        ))).all()
    assert approval.state == "PENDING"
    assert approval.verified_at is None
    assert not events


@pytest.mark.asyncio
async def test_api_missing_provider_returns_503_and_provider_client_cleanup(monkeypatch):
    require_test_database()
    monkeypatch.delenv("PAYPAL_SANDBOX_CLIENT_ID", raising=False)
    monkeypatch.delenv("PAYPAL_SANDBOX_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("PAYPAL_SANDBOX_MERCHANTS", raising=False)
    closed = []
    class Http:
        async def aclose(self): closed.append(True)
    class ApiPaypal(FakePayPal):
        status = "CREATED"
        async def get_order(self, *, order_id, expected_paypal_merchant_id, amount, currency):
            self.calls += 1
            return {"id": order_id, "status": self.status, "purchase_units": [{
                "payee": {"merchant_id": expected_paypal_merchant_id},
                "amount": {"currency_code": currency, "value": str(amount)},
            }]}
    from intentra.services import provider_runtime
    api_paypal = ApiPaypal()
    monkeypatch.setattr(provider_runtime, "build_checkout_providers", lambda: (registry(), api_paypal, Http()))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:3000", headers={"Origin": "http://localhost:3000"}) as client:
        reg = await client.post("/api/auth/register", json={"email": f"provider-{uuid.uuid4().hex}@example.com", "password": "IntentraIntegrationTest2026!"})
        assert reg.status_code == 201
        actor_id = uuid.UUID(reg.json()["id"])
        monkeypatch.setattr(provider_runtime, "build_checkout_providers", lambda: (_ for _ in ()).throw(provider_runtime.ProviderConfigurationError()))
        resp = await client.post("/api/payments/checkout", json={"attempt_id": str(uuid.uuid4())})
        assert resp.status_code == 503
        monkeypatch.setattr(provider_runtime, "build_checkout_providers", lambda: (registry(), api_paypal, Http()))

        contract_response = await client.post("/api/contracts", json={
            "merchant_id": "binding_test_merchant", "maximum_amount": "100.00", "currency": "USD",
        })
        assert contract_response.status_code == 201, contract_response.text
        contract_id = contract_response.json()["id"]
        approved = await client.post(f"/api/contracts/{contract_id}/approve", json={"expected_version": 1})
        assert approved.status_code == 200, approved.text
        reserved = await client.post("/api/payments/reserve", json={
            "contract_id": contract_id, "idempotency_key": f"client-{uuid.uuid4().hex}",
            "merchant_id": "binding_test_merchant", "amount": "40.00", "currency": "USD",
        })
        assert reserved.status_code == 200, reserved.text
        async with SessionLocal() as db:
            claim = await claim_payment_execution(db, reservation_id=uuid.UUID(reserved.json()["reservation_id"]), actor_id=actor_id)
        async with SessionLocal() as db:
            await bind_provider_order(db, attempt_id=claim.attempt_id, provider_order_id=f"MOCK-API-{uuid.uuid4().hex}")

        # Error and successful initiation both execute the yield-finalizer.
        failed = await client.post("/api/payments/checkout", json={"attempt_id": str(uuid.uuid4())})
        assert failed.status_code == 409
        succeeded = await client.post("/api/payments/checkout", json={"attempt_id": str(claim.attempt_id)})
        assert succeeded.status_code == 201, succeeded.text
        outsider = AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:3000", headers={"Origin": "http://localhost:3000"})
        async with outsider:
            outsider_reg = await outsider.post("/api/auth/register", json={"email": f"outsider-{uuid.uuid4().hex}@example.com", "password": "IntentraIntegrationTest2026!"})
            assert outsider_reg.status_code == 201
            denied = await outsider.post("/api/payments/checkout/return", json={
                "attempt_id": succeeded.json()["attempt_id"], "state": succeeded.json()["return_state"],
            })
            assert denied.status_code == 409
        api_paypal.status = "APPROVED"
        returned = await client.post("/api/payments/checkout/return", json={
            "attempt_id": succeeded.json()["attempt_id"], "state": succeeded.json()["return_state"],
        })
        assert returned.status_code == 200, returned.text
        assert returned.json()["state"] == "APPROVED"
    assert len(closed) == 4
