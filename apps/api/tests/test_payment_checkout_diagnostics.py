import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from test_contract_integration import app, require_test_database
from intentra.routes.payments import checkout_provider


async def _register(client: AsyncClient) -> None:
    result = await client.post("/api/auth/register", json={
        "email": f"checkout-diagnostic-{uuid.uuid4().hex}@example.com",
        "password": "IntentraIntegrationTest2026!",
    })
    assert result.status_code == 201, result.text


@pytest.mark.asyncio
async def test_checkout_auth_and_origin_rejections_have_stable_codes():
    require_test_database()
    correlation_id = str(uuid.uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:3000") as client:
        unauthenticated = await client.post(
            f"/api/payments/reservations/{uuid.uuid4()}/checkout",
            headers={"Origin": "http://localhost:3000",
                     "X-Intentra-Correlation-ID": correlation_id},
        )
        assert unauthenticated.status_code == 401
        assert unauthenticated.headers["X-Intentra-Error-Code"] == "AUTHENTICATION_REQUIRED"
        assert unauthenticated.headers["X-Intentra-Correlation-ID"] == correlation_id

        origin_rejected = await client.post(
            f"/api/payments/reservations/{uuid.uuid4()}/checkout",
            headers={"Origin": "https://attacker.invalid",
                     "X-Intentra-Correlation-ID": correlation_id},
        )
        assert origin_rejected.status_code == 403
        assert origin_rejected.headers["X-Intentra-Error-Code"] == "ORIGIN_REJECTED"
        assert origin_rejected.headers["X-Intentra-Correlation-ID"] == correlation_id
        assert origin_rejected.json()["code"] == "ORIGIN_REJECTED"

        generated = await client.post(
            f"/api/payments/reservations/{uuid.uuid4()}/checkout",
            headers={"Origin": "http://localhost:3000"},
        )
        assert uuid.UUID(generated.headers["X-Intentra-Correlation-ID"])


@pytest.mark.asyncio
async def test_missing_provider_configuration_is_distinguished_before_checkout(monkeypatch):
    require_test_database()
    from intentra.services import provider_runtime

    def unavailable():
        raise provider_runtime.ProviderConfigurationError()

    monkeypatch.setattr(provider_runtime, "build_checkout_providers", unavailable)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:3000",
                               headers={"Origin": "http://localhost:3000"}) as client:
            await _register(client)
            response = await client.post(
                f"/api/payments/reservations/{uuid.uuid4()}/checkout"
            )
        assert response.status_code == 503
        assert response.headers["X-Intentra-Error-Code"] == "CHECKOUT_PROVIDER_UNAVAILABLE"
        assert "secret" not in response.text.lower()
    finally:
        app.dependency_overrides.pop(checkout_provider, None)


@pytest.mark.asyncio
async def test_invalid_reservation_is_rejected_before_provider_order_call():
    require_test_database()
    calls = 0

    class NeverCalledPayPal:
        async def create_order(self, **_kwargs):
            nonlocal calls
            calls += 1
            raise AssertionError("provider must not be called for an invalid reservation")

    async def provider_override():
        from intentra.services.merchant_registry import TrustedMerchantRegistry
        yield TrustedMerchantRegistry({"demo": "PAYPAL-MERCHANT"}), NeverCalledPayPal()

    app.dependency_overrides[checkout_provider] = provider_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:3000",
                               headers={"Origin": "http://localhost:3000"}) as client:
            await _register(client)
            response = await client.post(
                f"/api/payments/reservations/{uuid.uuid4()}/checkout"
            )
        assert response.status_code == 409
        assert response.headers["X-Intentra-Error-Code"] == "PAYMENT_NOT_ELIGIBLE"
        assert uuid.UUID(response.headers["X-Intentra-Correlation-ID"])
        assert calls == 0
    finally:
        app.dependency_overrides.pop(checkout_provider, None)
