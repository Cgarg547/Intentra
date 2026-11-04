import uuid
from decimal import Decimal
from urllib.parse import parse_qs, urlsplit

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from test_contract_integration import app, require_test_database
from intentra.database import SessionLocal
from intentra.models.payment_attempt import PaymentAttemptRecord
from intentra.models.payment_checkout_approval import PaymentCheckoutApprovalRecord
from intentra.routes.payments import checkout_provider
from intentra.services.merchant_registry import TrustedMerchantRegistry


class CheckoutPayPal:
    def __init__(self):
        self.order_id = f"E2E-{uuid.uuid4().hex}"
        self.create_calls = 0
        self.return_url = None
        self.cancel_url = None

    async def create_order(self, *, amount, currency, provider_idempotency_key,
                           expected_paypal_merchant_id, return_url=None, cancel_url=None):
        self.create_calls += 1
        self.return_url, self.cancel_url = return_url, cancel_url
        return {
            "id": self.order_id,
            "status": "CREATED",
            "purchase_units": [{"payee": {"merchant_id": expected_paypal_merchant_id},
                "amount": {"currency_code": currency, "value": f"{amount:.2f}"}}],
            "links": [{"rel": "approve", "href": "https://www.sandbox.paypal.com/checkoutnow?token=MOCK"}],
        }

    async def get_order(self, *, order_id, expected_paypal_merchant_id, amount, currency):
        assert order_id == self.order_id
        return {"id": self.order_id, "status": "CREATED", "purchase_units": [{
            "payee": {"merchant_id": expected_paypal_merchant_id},
            "amount": {"currency_code": currency, "value": f"{amount:.2f}"},
        }]}


@pytest.mark.asyncio
async def test_reservation_checkout_creates_binds_and_persists_authenticated_handoff():
    require_test_database()
    suffix = uuid.uuid4().hex
    paypal = CheckoutPayPal()

    async def provider_override():
        yield TrustedMerchantRegistry({"binding_test_merchant": "PAYPAL-MERCHANT"}), paypal

    app.dependency_overrides[checkout_provider] = provider_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:3000",
                               headers={"Origin": "http://localhost:3000"}) as owner:
            registered = await owner.post("/api/auth/register", json={
                "email": f"frontend-flow-{suffix}@example.com",
                "password": "IntentraIntegrationTest2026!",
            })
            assert registered.status_code == 201, registered.text
            actor_id = uuid.UUID(registered.json()["id"])
            contract = await owner.post("/api/contracts", json={
                "merchant_id": "binding_test_merchant", "maximum_amount": "100.00", "currency": "USD",
            })
            assert contract.status_code == 201, contract.text
            contract_id = contract.json()["id"]
            approved = await owner.post(f"/api/contracts/{contract_id}/approve", json={"expected_version": 1})
            assert approved.status_code == 200, approved.text
            reserved = await owner.post("/api/payments/reserve", json={
                "contract_id": contract_id, "idempotency_key": f"frontend-flow-{suffix}",
                "merchant_id": "binding_test_merchant", "amount": "24.50", "currency": "USD",
            })
            assert reserved.status_code == 200, reserved.text
            response = await owner.post(f"/api/payments/reservations/{reserved.json()['reservation_id']}/checkout")
            assert response.status_code == 201, response.text
            result = response.json()
            assert result["approval_url"].startswith("https://www.sandbox.paypal.com/")
            assert result["provider_order_id"] == paypal.order_id
            assert result["state"] == "PENDING"
            assert result["return_state"]
            assert paypal.create_calls == 1
            assert parse_qs(urlsplit(paypal.return_url).query)["attempt_id"] == [result["attempt_id"]]
            assert parse_qs(urlsplit(paypal.cancel_url).query)["attempt_id"] == [result["attempt_id"]]

            history = await owner.get("/api/payments/history")
            assert history.status_code == 200
            assert history.json()["items"][0]["attempt_id"] == result["attempt_id"]
            reservation_history = await owner.get("/api/payments/reservations")
            assert reservation_history.status_code == 200
            assert reservation_history.json()["items"][0]["reservation_id"] == reserved.json()["reservation_id"]
            details = await owner.get(f"/api/payments/attempts/{result['attempt_id']}")
            assert details.status_code == 200
            assert any(event["event_type"] == "CHECKOUT_CREATED" for event in details.json()["events"])

            outsider = AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:3000",
                                   headers={"Origin": "http://localhost:3000"})
            async with outsider:
                outreg = await outsider.post("/api/auth/register", json={
                    "email": f"frontend-flow-outsider-{suffix}@example.com",
                    "password": "IntentraIntegrationTest2026!",
                })
                assert outreg.status_code == 201
                assert (await outsider.get(f"/api/payments/attempts/{result['attempt_id']}")).status_code == 404
                assert (await outsider.get("/api/payments/history")).json()["items"] == []
                assert (await outsider.get("/api/payments/reservations")).json()["items"] == []

        async with SessionLocal() as db:
            attempt = await db.get(PaymentAttemptRecord, uuid.UUID(result["attempt_id"]))
            approval = await db.scalar(select(PaymentCheckoutApprovalRecord).where(
                PaymentCheckoutApprovalRecord.attempt_id == attempt.id
            ))
            assert attempt.provider_order_id == paypal.order_id
            assert approval is not None
            assert approval.return_state_hash != result["return_state"]
            assert Decimal(approval.verified_amount or 0) == 0
    finally:
        app.dependency_overrides.pop(checkout_provider, None)
