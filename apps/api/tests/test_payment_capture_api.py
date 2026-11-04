import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from test_contract_integration import app, require_test_database
from test_payment_capture import MockPayPal, make_registry

from intentra.database import SessionLocal
from intentra.routes.payments import checkout_provider
from intentra.services.checkout_approval import initiate_checkout_approval, verify_checkout_return
from intentra.services.payment_execution import claim_payment_execution
from intentra.services.payment_order_binding import bind_provider_order
from intentra.services.paypal_sandbox import PayPalCaptureOutcomeUnknownError


@pytest.mark.asyncio
async def test_authenticated_capture_and_reconcile_endpoints_are_owner_scoped():
    require_test_database()
    suffix = uuid.uuid4().hex
    order_id = f"MOCK-API-CAPTURE-{suffix}"
    paypal = MockPayPal(order_id)

    async def provider_override():
        yield make_registry(), paypal

    app.dependency_overrides[checkout_provider] = provider_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:3000",
                               headers={"Origin": "http://localhost:3000"}) as owner:
            registered = await owner.post("/api/auth/register", json={
                "email": f"capture-api-{suffix}@example.com",
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
                "contract_id": contract_id, "idempotency_key": f"capture-api-{suffix}",
                "merchant_id": "binding_test_merchant", "amount": "40.00", "currency": "USD",
            })
            assert reserved.status_code == 200, reserved.text

            async with SessionLocal() as db:
                claim = await claim_payment_execution(db,
                    reservation_id=uuid.UUID(reserved.json()["reservation_id"]), actor_id=actor_id)
            async with SessionLocal() as db:
                await bind_provider_order(db, attempt_id=claim.attempt_id, provider_order_id=order_id)

            async with SessionLocal() as db:
                handoff = await initiate_checkout_approval(db, attempt_id=claim.attempt_id,
                    actor_id=actor_id, registry=make_registry(), paypal=paypal)
            paypal.order_status = "APPROVED"
            async with SessionLocal() as db:
                await verify_checkout_return(db, attempt_id=claim.attempt_id, actor_id=actor_id,
                    return_state=handoff.return_state, registry=make_registry(), paypal=paypal)

            # Provider may have completed capture while its response was lost.
            paypal.capture_error = PayPalCaptureOutcomeUnknownError("ambiguous response")
            captured = await owner.post(f"/api/payments/attempts/{claim.attempt_id}/capture")
            assert captured.status_code == 200, captured.text
            assert captured.json()["state"] == "UNKNOWN"
            assert captured.json()["capture_id"] is None

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:3000",
                                   headers={"Origin": "http://localhost:3000"}) as outsider:
                outreg = await outsider.post("/api/auth/register", json={
                    "email": f"capture-outsider-{suffix}@example.com",
                    "password": "IntentraIntegrationTest2026!",
                })
                assert outreg.status_code == 201
                denied = await outsider.post(f"/api/payments/attempts/{claim.attempt_id}/reconcile")
                assert denied.status_code == 409

            paypal.capture_error = None
            paypal.order_status = "COMPLETED"
            reconciled = await owner.post(f"/api/payments/attempts/{claim.attempt_id}/reconcile")
            assert reconciled.status_code == 200, reconciled.text
            assert reconciled.json()["action"] == "CAPTURE_COMPLETED"
            assert reconciled.json()["capture_id"] == paypal.capture_id
            assert paypal.capture_calls == 1
    finally:
        app.dependency_overrides.pop(checkout_provider, None)
