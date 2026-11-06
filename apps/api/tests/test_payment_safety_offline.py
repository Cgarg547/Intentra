"""Network- and database-free regression tests for payment safety boundaries."""

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
import hashlib
import uuid

import pytest

from intentra.services import checkout_approval
from intentra.services.checkout_approval import cancel_checkout, verify_checkout_return
from intentra.services.merchant_registry import TrustedMerchantRegistry
from intentra.services.payment_capture import claim_payment_capture
from intentra.services.payment_reconciliation_runner import reconcile_payment_attempt
from intentra.services.paypal_sandbox import PayPalSandboxError, validate_paypal_order


class FakeSession:
    def __init__(self, scalar_values=()):
        self._scalar_values = iter(scalar_values)
        self.events = []

    @asynccontextmanager
    async def begin(self):
        yield self

    async def scalar(self, _statement):
        return next(self._scalar_values)

    async def flush(self):
        return None

    def add(self, event):
        self.events.append(event)

    def expire_all(self):
        return None

    def in_transaction(self):
        return False


def _pending_checkout(*, expires_at):
    token = "state-token"
    attempt = SimpleNamespace(status="PENDING", provider_order_id="ORDER-1")
    reservation = SimpleNamespace(status="EXECUTION_PENDING")
    approval = SimpleNamespace(
        id=uuid.uuid4(), attempt_id=uuid.uuid4(), provider_order_id="ORDER-1",
        state="PENDING", consumed_at=None, expires_at=expires_at,
        return_state_hash=hashlib.sha256(token.encode()).hexdigest(),
        audit_correlation_id=uuid.uuid4(), verified_provider_status=None,
        verified_merchant_id=None, verified_amount=None, verified_currency=None,
        verified_at=None,
    )
    return token, attempt, reservation, approval


@pytest.mark.asyncio
@pytest.mark.parametrize("expired", [False, True])
async def test_cancel_or_expiry_consumes_approval_but_never_releases_pending_reservation(monkeypatch, expired):
    token, attempt, reservation, approval = _pending_checkout(
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)
        if expired else datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    db = FakeSession([approval])

    async def locked_records(*_args, **_kwargs):
        return SimpleNamespace(), reservation, attempt

    monkeypatch.setattr(checkout_approval, "_lock_current", locked_records)
    result = await cancel_checkout(
        db, attempt_id=approval.attempt_id, actor_id=uuid.uuid4(), return_state=token,
    )

    assert result.state == ("EXPIRED" if expired else "CANCELLED")
    assert approval.consumed_at is not None
    assert attempt.status == "PENDING"
    assert reservation.status == "EXECUTION_PENDING"


@pytest.mark.asyncio
async def test_expired_return_never_releases_pending_reservation(monkeypatch):
    token, attempt, reservation, approval = _pending_checkout(
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    contract = SimpleNamespace(status="APPROVED", version=1)
    db = FakeSession([approval])

    async def locked_records(*_args, **_kwargs):
        return contract, reservation, attempt

    monkeypatch.setattr(checkout_approval, "_lock_current", locked_records)
    result = await verify_checkout_return(
        db, attempt_id=approval.attempt_id, actor_id=uuid.uuid4(), return_state=token,
        registry=TrustedMerchantRegistry({"merchant": "PAYPAL-MERCHANT"}),
        paypal=SimpleNamespace(),
    )

    assert result.state == "EXPIRED"
    assert attempt.status == "PENDING"
    assert reservation.status == "EXECUTION_PENDING"


@pytest.mark.asyncio
async def test_capture_claim_moves_attempt_to_unknown_and_retains_reservation(monkeypatch):
    contract = SimpleNamespace(
        status="APPROVED", version=1, maximum_amount=Decimal("10.00"),
        merchant_id="merchant", currency="USD",
    )
    reservation = SimpleNamespace(
        status="EXECUTION_PENDING", contract_version=1, amount=Decimal("1.00"),
        currency="USD", merchant_id="merchant",
    )
    attempt = SimpleNamespace(
        id=uuid.uuid4(), status="PENDING", provider_order_id="ORDER-1",
        capture_claimed_at=None, capture_idempotency_key=None, capture_id=None,
    )
    approval = SimpleNamespace(
        id=uuid.uuid4(), state="APPROVED", consumed_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5), provider_order_id="ORDER-1",
        verified_provider_status="APPROVED", verified_amount=Decimal("1.00"),
        verified_currency="USD", verified_merchant_id="PAYPAL-MERCHANT",
    )
    db = FakeSession()

    async def locked_records(*_args, **_kwargs):
        return contract, reservation, attempt, approval

    monkeypatch.setattr("intentra.services.payment_capture._locked_records", locked_records)
    claim = await claim_payment_capture(
        db, attempt_id=attempt.id, actor_id=uuid.uuid4(),
        registry=TrustedMerchantRegistry({"merchant": "PAYPAL-MERCHANT"}),
    )

    assert claim.order_id == "ORDER-1"
    assert attempt.status == "UNKNOWN"
    assert reservation.status == "OUTCOME_UNKNOWN"
    assert attempt.capture_claimed_at is not None
    assert attempt.capture_idempotency_key


class LookupOnlyPayPal:
    def __init__(self, payload):
        self.payload = payload
        self.get_calls = 0
        self.create_calls = 0
        self.capture_calls = 0

    async def get_order(self, *, order_id, expected_paypal_merchant_id, amount, currency):
        self.get_calls += 1
        validate_paypal_order(
            self.payload, order_id=order_id,
            expected_paypal_merchant_id=expected_paypal_merchant_id,
            amount=amount, currency=currency,
        )
        return self.payload

    async def create_order(self, **_kwargs):
        self.create_calls += 1
        raise AssertionError("Reconciliation must never create an order")

    async def capture_order(self, **_kwargs):
        self.capture_calls += 1
        raise AssertionError("Reconciliation must never capture an order")


def _pending_attempt_records():
    attempt = SimpleNamespace(
        id=uuid.uuid4(), reservation_id=uuid.uuid4(), status="PENDING",
        provider_order_id="ORDER-1", capture_claimed_at=None,
        capture_idempotency_key=None, capture_id=None,
    )
    reservation = SimpleNamespace(
        id=attempt.reservation_id, contract_id=uuid.uuid4(), contract_version=1,
        status="EXECUTION_PENDING", merchant_id="merchant", amount=Decimal("1.00"),
        currency="USD", actor_id=uuid.uuid4(),
    )
    return attempt, reservation


def _order_payload(**changes):
    unit = {
        "payee": {"merchant_id": "PAYPAL-MERCHANT"},
        "amount": {"currency_code": "USD", "value": "1.00"},
    }
    payload = {"id": "ORDER-1", "status": "CREATED", "purchase_units": [unit]}
    for path, value in changes.items():
        if path == "merchant":
            unit["payee"]["merchant_id"] = value
        elif path == "amount":
            unit["amount"]["value"] = value
        elif path == "currency":
            unit["amount"]["currency_code"] = value
        else:
            payload[path] = value
    return payload


@pytest.mark.asyncio
async def test_repeated_reconciliation_uses_lookup_only(monkeypatch):
    attempt, reservation = _pending_attempt_records()
    paypal = LookupOnlyPayPal(_order_payload())

    async def reconcile_once():
        db = FakeSession([attempt, reservation, attempt, reservation])
        return await reconcile_payment_attempt(
            db, attempt_id=attempt.id,
            registry=TrustedMerchantRegistry({"merchant": "PAYPAL-MERCHANT"}),
            paypal=paypal,
        )

    first, second = await reconcile_once(), await reconcile_once()
    assert first.action == second.action == "ORDER_VERIFIED"
    assert paypal.get_calls == 2
    assert paypal.create_calls == 0
    assert paypal.capture_calls == 0
    assert attempt.status == "PENDING"
    assert reservation.status == "EXECUTION_PENDING"


@pytest.mark.asyncio
@pytest.mark.parametrize("change", [
    {"merchant": "OTHER-MERCHANT"},
    {"amount": "2.00"},
    {"currency": "CAD"},
    {"id": "OTHER-ORDER"},
])
async def test_reconciliation_provider_identity_mismatches_fail_closed(change):
    attempt, reservation = _pending_attempt_records()
    paypal = LookupOnlyPayPal(_order_payload(**change))
    db = FakeSession([attempt, reservation])

    with pytest.raises(PayPalSandboxError):
        await reconcile_payment_attempt(
            db, attempt_id=attempt.id,
            registry=TrustedMerchantRegistry({"merchant": "PAYPAL-MERCHANT"}),
            paypal=paypal,
        )

    assert paypal.get_calls == 1
    assert paypal.create_calls == 0
    assert paypal.capture_calls == 0
    assert attempt.status == "PENDING"
    assert reservation.status == "EXECUTION_PENDING"
