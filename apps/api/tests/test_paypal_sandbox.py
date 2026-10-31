from decimal import Decimal

import httpx
import pytest

from intentra.services.paypal_sandbox import (
    PayPalSandboxClient,
    PayPalSandboxConfig,
    PayPalSandboxError,
)


def make_client(handler):
    http = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
    )
    paypal = PayPalSandboxClient(
        PayPalSandboxConfig(
            client_id="test-client",
            client_secret="test-secret",
        ),
        http_client=http,
    )
    return paypal, http


@pytest.mark.asyncio
async def test_paypal_oauth_authentication():
    def handler(request):
        assert request.method == "POST"
        assert request.url.path == "/v1/oauth2/token"
        assert request.url.host == "api-m.sandbox.paypal.com"
        assert request.headers["Authorization"].startswith("Basic ")
        assert b"client_credentials" in request.content

        return httpx.Response(
            200,
            json={"access_token": "mock-access-token"},
        )

    paypal, http = make_client(handler)

    async with http:
        token = await paypal.get_access_token()

    assert token == "mock-access-token"


@pytest.mark.asyncio
async def test_paypal_order_creation_uses_idempotency():
    import json

    def handler(request):
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(
                200,
                json={"access_token": "mock-token"},
            )

        assert request.method == "POST"
        assert request.url.path == "/v2/checkout/orders"
        assert request.headers["PayPal-Request-Id"] == "intentra-test-123"
        assert request.headers["Authorization"] == "Bearer mock-token"

        payload = json.loads(request.content)
        assert payload["intent"] == "CAPTURE"
        assert payload["purchase_units"][0]["amount"] == {
            "currency_code": "USD",
            "value": "40.00",
        }

        return httpx.Response(
            201,
            json={
                "id": "MOCK-ORDER-123",
                "status": "CREATED",
            },
        )

    paypal, http = make_client(handler)

    async with http:
        order = await paypal.create_order(
            amount=Decimal("40.00"),
            currency="USD",
            provider_idempotency_key="intentra-test-123",
        )

    assert order["id"] == "MOCK-ORDER-123"


@pytest.mark.asyncio
async def test_paypal_order_lookup():
    def handler(request):
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(
                200,
                json={"access_token": "mock-token"},
            )

        assert request.method == "GET"
        assert request.url.path == "/v2/checkout/orders/MOCK-123"

        return httpx.Response(
            200,
            json={
                "id": "MOCK-123",
                "status": "COMPLETED",
            },
        )

    paypal, http = make_client(handler)

    async with http:
        order = await paypal.get_order(order_id="MOCK-123")

    assert order["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_paypal_rejects_invalid_amount():
    def handler(request):
        raise AssertionError("No HTTP request should be made")

    paypal, http = make_client(handler)

    async with http:
        with pytest.raises(PayPalSandboxError):
            await paypal.create_order(
                amount=Decimal("-5.00"),
                currency="USD",
                provider_idempotency_key="invalid-test",
            )


@pytest.mark.asyncio
async def test_paypal_authentication_failure():
    def handler(request):
        return httpx.Response(
            401,
            json={"error": "invalid_client"},
        )

    paypal, http = make_client(handler)

    async with http:
        with pytest.raises(
            PayPalSandboxError,
            match="authentication failed",
        ):
            await paypal.get_access_token()


@pytest.mark.asyncio
async def test_paypal_order_timeout_is_reported_as_uncertain():
    def handler(request):
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(
                200,
                json={"access_token": "mock-token"},
            )

        raise httpx.ReadTimeout("Simulated lost provider response")

    paypal, http = make_client(handler)

    async with http:
        with pytest.raises(
            PayPalSandboxError,
            match="outcome unknown",
        ):
            await paypal.create_order(
                amount=Decimal("40.00"),
                currency="USD",
                provider_idempotency_key="intentra-timeout-test",
            )


@pytest.mark.asyncio
async def test_paypal_invalid_order_response_is_rejected():
    def handler(request):
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(
                200,
                json={"access_token": "mock-token"},
            )

        return httpx.Response(
            201,
            json={"id": 123, "status": "CREATED"},
        )

    paypal, http = make_client(handler)

    async with http:
        with pytest.raises(
            PayPalSandboxError,
            match="invalid order",
        ):
            await paypal.create_order(
                amount=Decimal("40.00"),
                currency="USD",
                provider_idempotency_key="intentra-invalid-response",
            )


@pytest.mark.asyncio
async def test_paypal_order_server_error_is_uncertain():
    def handler(request):
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(
                200,
                json={"access_token": "mock-token"},
            )

        return httpx.Response(
            500,
            json={"name": "INTERNAL_SERVER_ERROR"},
        )

    paypal, http = make_client(handler)

    async with http:
        with pytest.raises(
            PayPalSandboxError,
            match="outcome unknown",
        ):
            await paypal.create_order(
                amount=Decimal("40.00"),
                currency="USD",
                provider_idempotency_key="intentra-server-error",
            )


@pytest.mark.asyncio
async def test_paypal_order_malformed_json_is_rejected():
    def handler(request):
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(
                200,
                json={"access_token": "mock-token"},
            )

        return httpx.Response(
            201,
            text="not valid json",
        )

    paypal, http = make_client(handler)

    async with http:
        with pytest.raises(
            PayPalSandboxError,
            match="outcome unknown",
        ):
            await paypal.create_order(
                amount=Decimal("40.00"),
                currency="USD",
                provider_idempotency_key="intentra-malformed-json",
            )
