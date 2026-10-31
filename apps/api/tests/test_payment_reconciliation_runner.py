import uuid

import httpx
import pytest
from sqlalchemy import select

from test_payment_order_binding import create_claimed_attempt
from test_contract_integration import require_test_database

from intentra.database import SessionLocal
from intentra.models.payment_attempt import PaymentAttemptRecord
from intentra.models.payment_reservation import PaymentReservationRecord
from intentra.services.merchant_registry import TrustedMerchantRegistry
from intentra.services.payment_order_binding import bind_provider_order
from intentra.services.payment_reconciliation import PaymentReconciliationError
from intentra.services.payment_reconciliation_runner import (
    reconcile_payment_attempt,
)
from intentra.services.paypal_sandbox import (
    PayPalSandboxClient,
    PayPalSandboxConfig,
    PayPalSandboxError,
)


def make_paypal(handler):
    http = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
    )
    paypal = PayPalSandboxClient(
        PayPalSandboxConfig("test-client", "test-secret"),
        http_client=http,
    )
    return paypal, http


@pytest.mark.asyncio
async def test_unknown_order_id_makes_no_paypal_request():
    require_test_database()
    attempt_id = await create_claimed_attempt()

    def handler(request):
        raise AssertionError("No PayPal HTTP call is allowed")

    paypal, http = make_paypal(handler)
    registry = TrustedMerchantRegistry({})

    async with http, SessionLocal() as db:
        result = await reconcile_payment_attempt(
            db,
            attempt_id=attempt_id,
            registry=registry,
            paypal=paypal,
        )

    assert result.action == "HOLD_FOR_REVIEW"
    assert result.provider_order_id is None

    async with SessionLocal() as db:
        attempt = await db.scalar(
            select(PaymentAttemptRecord).where(
                PaymentAttemptRecord.id == attempt_id
            )
        )
        reservation = await db.scalar(
            select(PaymentReservationRecord).where(
                PaymentReservationRecord.id == attempt.reservation_id
            )
        )

    assert attempt.status == "PENDING"
    assert reservation.status == "EXECUTION_PENDING"


@pytest.mark.asyncio
async def test_known_order_is_verified_without_state_change():
    require_test_database()
    attempt_id = await create_claimed_attempt()
    order_id = f"MOCK-{uuid.uuid4().hex}"

    async with SessionLocal() as db:
        await bind_provider_order(
            db,
            attempt_id=attempt_id,
            provider_order_id=order_id,
        )

    def handler(request):
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(
                200,
                json={"access_token": "mock-token"},
            )

        assert request.method == "GET"
        assert request.url.path.endswith(f"/{order_id}")

        return httpx.Response(
            200,
            json={
                "id": order_id,
                "status": "CREATED",
                "purchase_units": [
                    {
                        "payee": {
                            "merchant_id": "VERIFIED_PAYPAL_ACCOUNT",
                        },
                        "amount": {
                            "currency_code": "USD",
                            "value": "40.00",
                        },
                    }
                ],
            },
        )

    paypal, http = make_paypal(handler)
    registry = TrustedMerchantRegistry({
        "binding_test_merchant": "VERIFIED_PAYPAL_ACCOUNT",
    })

    async with http, SessionLocal() as db:
        result = await reconcile_payment_attempt(
            db,
            attempt_id=attempt_id,
            registry=registry,
            paypal=paypal,
        )

    assert result.action == "ORDER_VERIFIED"
    assert result.provider_order_id == order_id
    assert result.provider_status == "CREATED"

    async with SessionLocal() as db:
        attempt = await db.scalar(
            select(PaymentAttemptRecord).where(
                PaymentAttemptRecord.id == attempt_id
            )
        )
        reservation = await db.scalar(
            select(PaymentReservationRecord).where(
                PaymentReservationRecord.id == attempt.reservation_id
            )
        )

    assert attempt.status == "PENDING"
    assert reservation.status == "EXECUTION_PENDING"


@pytest.mark.asyncio
async def test_mismatched_provider_order_does_not_change_state():
    require_test_database()
    attempt_id = await create_claimed_attempt()
    order_id = f"MOCK-{uuid.uuid4().hex}"

    async with SessionLocal() as db:
        await bind_provider_order(
            db,
            attempt_id=attempt_id,
            provider_order_id=order_id,
        )

    def handler(request):
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(
                200,
                json={"access_token": "mock-token"},
            )

        return httpx.Response(
            200,
            json={
                "id": order_id,
                "status": "CREATED",
                "purchase_units": [
                    {
                        "payee": {"merchant_id": "ATTACKER_ACCOUNT"},
                        "amount": {
                            "currency_code": "USD",
                            "value": "40.00",
                        },
                    }
                ],
            },
        )

    paypal, http = make_paypal(handler)
    registry = TrustedMerchantRegistry({
        "binding_test_merchant": "VERIFIED_PAYPAL_ACCOUNT",
    })

    async with http, SessionLocal() as db:
        with pytest.raises(
            PayPalSandboxError,
            match="merchant mismatch",
        ):
            await reconcile_payment_attempt(
                db,
                attempt_id=attempt_id,
                registry=registry,
                paypal=paypal,
            )

    async with SessionLocal() as db:
        attempt = await db.scalar(
            select(PaymentAttemptRecord).where(
                PaymentAttemptRecord.id == attempt_id
            )
        )
        reservation = await db.scalar(
            select(PaymentReservationRecord).where(
                PaymentReservationRecord.id == attempt.reservation_id
            )
        )

    assert attempt.status == "PENDING"
    assert reservation.status == "EXECUTION_PENDING"


@pytest.mark.asyncio
async def test_concurrent_reservation_change_rejects_stale_lookup():
    require_test_database()
    attempt_id = await create_claimed_attempt()
    order_id = f"MOCK-{uuid.uuid4().hex}"

    async with SessionLocal() as db:
        await bind_provider_order(
            db,
            attempt_id=attempt_id,
            provider_order_id=order_id,
        )

    async with SessionLocal() as db:
        attempt = await db.get(PaymentAttemptRecord, attempt_id)
        reservation_id = attempt.reservation_id

    async def handler(request):
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(
                200,
                json={"access_token": "mock-token"},
            )

        assert request.method == "GET"
        assert request.url.path.endswith(f"/{order_id}")

        # Simulate a separate transaction modifying the
        # reservation while the PayPal lookup is in progress.
        async with SessionLocal() as other_db:
            async with other_db.begin():
                reservation = await other_db.get(
                    PaymentReservationRecord,
                    reservation_id,
                )
                reservation.amount = reservation.amount + 1

        return httpx.Response(
            200,
            json={
                "id": order_id,
                "status": "CREATED",
                "purchase_units": [
                    {
                        "payee": {
                            "merchant_id": "VERIFIED_PAYPAL_ACCOUNT",
                        },
                        "amount": {
                            "currency_code": "USD",
                            "value": "40.00",
                        },
                    }
                ],
            },
        )

    paypal, http = make_paypal(handler)
    registry = TrustedMerchantRegistry({
        "binding_test_merchant": "VERIFIED_PAYPAL_ACCOUNT",
    })

    async with http, SessionLocal() as db:
        with pytest.raises(
            PaymentReconciliationError,
            match="Payment state changed during provider lookup",
        ):
            await reconcile_payment_attempt(
                db,
                attempt_id=attempt_id,
                registry=registry,
                paypal=paypal,
            )

    async with SessionLocal() as db:
        attempt = await db.get(PaymentAttemptRecord, attempt_id)
        reservation = await db.get(
            PaymentReservationRecord,
            reservation_id,
        )

    assert attempt.status == "PENDING"
    assert reservation.status == "EXECUTION_PENDING"
    assert reservation.amount == 41
