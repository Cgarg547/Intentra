from decimal import Decimal

import httpx
import pytest

from intentra.services.paypal_sandbox import (
    PayPalOrderNotSubmittedError,
    PayPalOrderOutcomeUnknownError,
    PayPalOrderRejectedError,
    PayPalSandboxClient,
    PayPalSandboxConfig,
    PayPalSandboxError,
)
from intentra.services.payment_orchestration import _approval_url


def capture_order_payload(status="COMPLETED", order_status="COMPLETED"):
    return {
        "id": "MOCK-ORDER-CAPTURE",
        "status": order_status,
        "purchase_units": [{
            "payee": {"merchant_id": "TEST_MERCHANT"},
            "amount": {"currency_code": "USD", "value": "40.00"},
            "payments": {"captures": [{
                "id": "MOCK-CAPTURE-123",
                "status": status,
                "amount": {"currency_code": "USD", "value": "40.00"},
            }]},
        }],
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("capture_status", ["COMPLETED", "PENDING", "DECLINED", "FAILED"])
async def test_paypal_capture_validates_identity_and_preserves_provider_ids(capture_status):
    def handler(request):
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(200, json={"access_token": "mock-token"})
        assert request.method == "POST"
        assert request.url.path == "/v2/checkout/orders/MOCK-ORDER-CAPTURE/capture"
        assert request.headers["Authorization"] == "Bearer mock-token"
        assert request.headers["PayPal-Request-Id"] == "capturekey123"
        return httpx.Response(201, json=capture_order_payload(capture_status))

    paypal, http = make_client(handler)
    async with http:
        result = await paypal.capture_order(
            order_id="MOCK-ORDER-CAPTURE",
            expected_paypal_merchant_id="TEST_MERCHANT",
            amount=Decimal("40.00"), currency="USD",
            provider_idempotency_key="capturekey123",
        )
    assert result["id"] == "MOCK-ORDER-CAPTURE"
    assert result["purchase_units"][0]["payments"]["captures"][0]["id"] == "MOCK-CAPTURE-123"
    assert result["purchase_units"][0]["payments"]["captures"][0]["status"] == capture_status


@pytest.mark.asyncio
async def test_paypal_already_captured_order_returns_validated_capture():
    def handler(request):
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(200, json={"access_token": "mock-token"})
        return httpx.Response(422, json={"name": "ORDER_ALREADY_CAPTURED"})

    paypal, http = make_client(handler)
    async with http:
        with pytest.raises(PayPalSandboxError, match="outcome unknown"):
            await paypal.capture_order(
                order_id="MOCK-ORDER-CAPTURE",
                expected_paypal_merchant_id="TEST_MERCHANT",
                amount=Decimal("40.00"), currency="USD",
                provider_idempotency_key="capturekey123",
            )


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["timeout", "connection"])
async def test_paypal_capture_network_failure_is_uncertain(failure):
    def handler(request):
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(200, json={"access_token": "mock-token"})
        if failure == "timeout":
            raise httpx.ReadTimeout("simulated")
        raise httpx.ConnectError("simulated", request=request)

    paypal, http = make_client(handler)
    async with http:
        with pytest.raises(PayPalSandboxError, match="outcome unknown"):
            await paypal.capture_order(
                order_id="MOCK-ORDER-CAPTURE",
                expected_paypal_merchant_id="TEST_MERCHANT",
                amount=Decimal("40.00"), currency="USD",
                provider_idempotency_key="capturekey123",
            )


@pytest.mark.asyncio
async def test_paypal_capture_authentication_failure_stops_before_capture():
    def handler(request):
        return httpx.Response(401, json={"error": "invalid_client"})

    paypal, http = make_client(handler)
    async with http:
        with pytest.raises(PayPalSandboxError, match="authentication failed"):
            await paypal.capture_order(
                order_id="MOCK-ORDER-CAPTURE",
                expected_paypal_merchant_id="TEST_MERCHANT",
                amount=Decimal("40.00"), currency="USD",
                provider_idempotency_key="capturekey123",
            )


@pytest.mark.asyncio
@pytest.mark.parametrize("response", [
    {},
    {"id": "WRONG", "purchase_units": []},
    {**capture_order_payload(), "purchase_units": [{**capture_order_payload()["purchase_units"][0], "payments": {"captures": []}}]},
    {**capture_order_payload(), "purchase_units": [{**capture_order_payload()["purchase_units"][0], "payments": {"captures": [{"id": "", "status": "COMPLETED"}]}}]},
])
async def test_paypal_capture_rejects_invalid_success_response(response):
    def handler(request):
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(200, json={"access_token": "mock-token"})
        return httpx.Response(200, json=response)

    paypal, http = make_client(handler)
    async with http:
        with pytest.raises(PayPalSandboxError):
            await paypal.capture_order(
                order_id="MOCK-ORDER-CAPTURE",
                expected_paypal_merchant_id="TEST_MERCHANT",
                amount=Decimal("40.00"), currency="USD",
                provider_idempotency_key="capturekey123",
            )


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [123, None, [], {}])
async def test_paypal_capture_rejects_non_string_status(status):
    payload = capture_order_payload(status=status)
    def handler(request):
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(200, json={"access_token": "mock-token"})
        return httpx.Response(200, json=payload)
    paypal, http = make_client(handler)
    async with http:
        with pytest.raises(PayPalSandboxError):
            await paypal.capture_order(
                order_id="MOCK-ORDER-CAPTURE",
                expected_paypal_merchant_id="TEST_MERCHANT",
                amount=Decimal("40.00"), currency="USD",
                provider_idempotency_key="capturekey123",
            )


@pytest.mark.asyncio
@pytest.mark.parametrize("mutate", [
    lambda p: p.update(purchase_units=None),
    lambda p: p.update(purchase_units=[None]),
    lambda p: p["purchase_units"][0].update(payments=[]),
    lambda p: p["purchase_units"][0].update(payments={"captures": None}),
    lambda p: p["purchase_units"][0].update(payments={"captures": [None]}),
])
async def test_paypal_capture_malformed_nested_data_raises_domain_error(mutate):
    payload = capture_order_payload()
    mutate(payload)
    def handler(request):
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(200, json={"access_token": "mock-token"})
        return httpx.Response(200, json=payload)
    paypal, http = make_client(handler)
    async with http:
        with pytest.raises(PayPalSandboxError):
            await paypal.capture_order(
                order_id="MOCK-ORDER-CAPTURE",
                expected_paypal_merchant_id="TEST_MERCHANT",
                amount=Decimal("40.00"), currency="USD",
                provider_idempotency_key="capturekey123",
            )


@pytest.mark.asyncio
@pytest.mark.parametrize("merchant,amount,currency", [
    ("OTHER", "40.00", "USD"),
    ("TEST_MERCHANT", "41.00", "USD"),
    ("TEST_MERCHANT", "40.00", "USＤ"),
])
async def test_paypal_capture_rejects_merchant_amount_currency_mismatch(merchant, amount, currency):
    payload = capture_order_payload()
    unit = payload["purchase_units"][0]
    unit["payee"]["merchant_id"] = merchant
    unit["amount"] = {"currency_code": currency, "value": amount}
    def handler(request):
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(200, json={"access_token": "mock-token"})
        return httpx.Response(200, json=payload)
    paypal, http = make_client(handler)
    async with http:
        with pytest.raises(PayPalSandboxError):
            await paypal.capture_order(
                order_id="MOCK-ORDER-CAPTURE",
                expected_paypal_merchant_id="TEST_MERCHANT",
                amount=Decimal("40.00"), currency="USD",
                provider_idempotency_key="capturekey123",
            )


@pytest.mark.asyncio
@pytest.mark.parametrize("value", ["NaN", "Infinity", "40.001", "invalid"])
async def test_paypal_capture_rejects_invalid_capture_decimal(value):
    payload = capture_order_payload()
    payload["purchase_units"][0]["payments"]["captures"][0]["amount"]["value"] = value
    def handler(request):
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(200, json={"access_token": "mock-token"})
        return httpx.Response(200, json=payload)
    paypal, http = make_client(handler)
    async with http:
        with pytest.raises(PayPalSandboxError):
            await paypal.capture_order(
                order_id="MOCK-ORDER-CAPTURE",
                expected_paypal_merchant_id="TEST_MERCHANT",
                amount=Decimal("40.00"), currency="USD",
                provider_idempotency_key="capturekey123",
            )


@pytest.mark.asyncio
@pytest.mark.parametrize("currency", ["USＤ", "UKD", "usd", "US1"])
async def test_paypal_capture_rejects_invalid_currency_characters(currency):
    paypal, http = make_client(lambda request: httpx.Response(500))
    async with http:
        with pytest.raises(PayPalSandboxError, match="currency"):
            await paypal.capture_order(
                order_id="MOCK-ORDER-CAPTURE",
                expected_paypal_merchant_id="TEST_MERCHANT",
                amount=Decimal("40.00"), currency=currency,
                provider_idempotency_key="capturekey123",
            )


@pytest.mark.asyncio
@pytest.mark.parametrize("key", ["", "contains space", "bad-key", "x" * 109, "ＫEY"])
async def test_paypal_capture_rejects_invalid_idempotency_key(key):
    paypal, http = make_client(lambda request: httpx.Response(500))
    async with http:
        with pytest.raises(PayPalSandboxError, match="idempotency"):
            await paypal.capture_order(
                order_id="MOCK-ORDER-CAPTURE",
                expected_paypal_merchant_id="TEST_MERCHANT",
                amount=Decimal("40.00"), currency="USD",
                provider_idempotency_key=key,
            )


@pytest.mark.asyncio
async def test_paypal_capture_provider_http_error_is_uncertain():
    def handler(request):
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(200, json={"access_token": "mock-token"})
        return httpx.Response(500, json={"name": "INTERNAL_SERVER_ERROR"})

    paypal, http = make_client(handler)
    async with http:
        with pytest.raises(PayPalSandboxError, match="outcome unknown"):
            await paypal.capture_order(
                order_id="MOCK-ORDER-CAPTURE",
                expected_paypal_merchant_id="TEST_MERCHANT",
                amount=Decimal("40.00"), currency="USD",
                provider_idempotency_key="capturekey123",
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
async def test_create_order_includes_paypal_experience_context_return_and_cancel_urls():
    def handler(request):
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(200, json={"access_token": "mock-token"})
        assert request.url.path == "/v2/checkout/orders"
        payload = request.read()
        import json
        body = json.loads(payload)
        context = body["payment_source"]["paypal"]["experience_context"]
        assert context["return_url"] == "http://localhost:3000/checkout/return?attempt_id=test-attempt"
        assert context["cancel_url"] == "http://localhost:3000/checkout/cancel?attempt_id=test-attempt"
        assert body["intent"] == "CAPTURE"
        return httpx.Response(201, json={
            "id": "MOCK-CHECKOUT-ORDER", "status": "CREATED",
            "purchase_units": [{
                "payee": {"merchant_id": "TEST_MERCHANT"},
                "amount": {"currency_code": "USD", "value": "40.00"},
            }],
            "links": [{"rel": "payer-action", "href": "https://www.sandbox.paypal.com/checkoutnow?token=MOCK"}],
        })

    paypal, http = make_client(handler)
    async with http:
        order = await paypal.create_order(
            amount=Decimal("40.00"), currency="USD",
            provider_idempotency_key="orderidempotencykey1",
            expected_paypal_merchant_id="TEST_MERCHANT",
            return_url="http://localhost:3000/checkout/return?attempt_id=test-attempt",
            cancel_url="http://localhost:3000/checkout/cancel?attempt_id=test-attempt",
        )
    assert order["id"] == "MOCK-CHECKOUT-ORDER"


@pytest.mark.asyncio
async def test_create_order_accepts_http_200_payer_action_required_and_payer_action_link():
    def handler(request):
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(200, json={"access_token": "mock-token"})
        assert request.method == "POST"
        assert request.url.path == "/v2/checkout/orders"
        return httpx.Response(200, json={
            "id": "MOCK-PAYER-ACTION-ORDER",
            "status": "PAYER_ACTION_REQUIRED",
            "purchase_units": [{
                "payee": {"merchant_id": "TEST_MERCHANT"},
                "amount": {"currency_code": "USD", "value": "1.00"},
            }],
            "links": [{
                "rel": "payer-action",
                "href": "https://www.sandbox.paypal.com/checkoutnow?token=MOCK",
            }],
        })

    paypal, http = make_client(handler)
    async with http:
        order = await paypal.create_order(
            amount=Decimal("1.00"), currency="USD",
            provider_idempotency_key="payeractionorderkey1",
            expected_paypal_merchant_id="TEST_MERCHANT",
        )

    assert order["id"] == "MOCK-PAYER-ACTION-ORDER"
    assert order["status"] == "PAYER_ACTION_REQUIRED"
    assert _approval_url(order) == "https://www.sandbox.paypal.com/checkoutnow?token=MOCK"


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
                "purchase_units": [
                    {
                        "payee": {
                            "merchant_id": "TEST_MERCHANT",
                        },
                        "amount": {
                            "currency_code": "USD",
                            "value": "40.00",
                        }
                    }
                ],
            },
        )

    paypal, http = make_client(handler)

    async with http:
        order = await paypal.create_order(
            amount=Decimal("40.00"),
            currency="USD",
            provider_idempotency_key="intentra-test-123",
            expected_paypal_merchant_id="TEST_MERCHANT",
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
                "status": "CREATED",
                "purchase_units": [
                    {
                        "payee": {"merchant_id": "TEST_MERCHANT"},
                        "amount": {
                            "currency_code": "USD",
                            "value": "40.00",
                        },
                    }
                ],
            },
        )

    paypal, http = make_client(handler)

    async with http:
        order = await paypal.get_order(
            order_id="MOCK-123",
            expected_paypal_merchant_id="TEST_MERCHANT",
            amount=Decimal("40.00"),
            currency="USD",
        )

    assert order["id"] == "MOCK-123"
    assert order["status"] == "CREATED"


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
                expected_paypal_merchant_id="TEST_MERCHANT",
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
            PayPalOrderOutcomeUnknownError,
            match="outcome unknown",
        ):
            await paypal.create_order(
                amount=Decimal("40.00"),
                currency="USD",
                provider_idempotency_key="intentra-timeout-test",
                expected_paypal_merchant_id="TEST_MERCHANT",
            )


@pytest.mark.asyncio
async def test_paypal_order_rejection_is_definite_and_sanitized():
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(200, json={"access_token": "mock-token"})
        return httpx.Response(422, json={"name": "INVALID_REQUEST", "message": "sensitive provider body"})

    paypal, http = make_client(handler)
    async with http:
        with pytest.raises(PayPalOrderRejectedError) as error:
            await paypal.create_order(amount=Decimal("40.00"), currency="USD",
                provider_idempotency_key="intentra-rejected-create",
                expected_paypal_merchant_id="TEST_MERCHANT")
    assert error.value.status_code == 422
    assert "sensitive provider body" not in str(error.value)
    assert calls == ["/v1/oauth2/token", "/v2/checkout/orders"]


@pytest.mark.asyncio
async def test_paypal_authentication_failure_means_order_was_not_submitted():
    calls = []

    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(401, json={"name": "AUTHENTICATION_FAILURE"})

    paypal, http = make_client(handler)
    async with http:
        with pytest.raises(PayPalOrderNotSubmittedError):
            await paypal.create_order(amount=Decimal("40.00"), currency="USD",
                provider_idempotency_key="intentra-auth-failure",
                expected_paypal_merchant_id="TEST_MERCHANT")
    assert calls == ["/v1/oauth2/token"]


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
                expected_paypal_merchant_id="TEST_MERCHANT",
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
                expected_paypal_merchant_id="TEST_MERCHANT",
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
                expected_paypal_merchant_id="TEST_MERCHANT",
            )


@pytest.mark.asyncio
async def test_paypal_rejects_order_with_mismatched_amount():
    def handler(request):
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(
                200,
                json={"access_token": "mock-token"},
            )

        return httpx.Response(
            201,
            json={
                "id": "MOCK-WRONG-AMOUNT",
                "status": "CREATED",
                "purchase_units": [
                    {
                        "payee": {"merchant_id": "TEST_MERCHANT"},
                        "amount": {
                            "currency_code": "USD",
                            "value": "90.00",
                        }
                    }
                ],
            },
        )

    paypal, http = make_client(handler)

    async with http:
        with pytest.raises(
            PayPalSandboxError,
            match="amount mismatch",
        ):
            await paypal.create_order(
                amount=Decimal("40.00"),
                currency="USD",
                provider_idempotency_key="intentra-amount-check",
                expected_paypal_merchant_id="TEST_MERCHANT",
            )


@pytest.mark.asyncio
async def test_paypal_rejects_order_with_mismatched_currency():
    def handler(request):
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(
                200,
                json={"access_token": "mock-token"},
            )

        return httpx.Response(
            201,
            json={
                "id": "MOCK-WRONG-CURRENCY",
                "status": "CREATED",
                "purchase_units": [
                    {
                        "payee": {"merchant_id": "TEST_MERCHANT"},
                        "amount": {
                            "currency_code": "CAD",
                            "value": "40.00",
                        }
                    }
                ],
            },
        )

    paypal, http = make_client(handler)

    async with http:
        with pytest.raises(
            PayPalSandboxError,
            match="currency mismatch",
        ):
            await paypal.create_order(
                amount=Decimal("40.00"),
                currency="USD",
                provider_idempotency_key="intentra-currency-check",
                expected_paypal_merchant_id="TEST_MERCHANT",
            )


@pytest.mark.asyncio
async def test_paypal_rejects_order_with_mismatched_merchant():
    def handler(request):
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(
                200,
                json={"access_token": "mock-token"},
            )

        return httpx.Response(
            201,
            json={
                "id": "MOCK-WRONG-MERCHANT",
                "status": "CREATED",
                "purchase_units": [
                    {
                        "payee": {
                            "merchant_id": "UNEXPECTED_MERCHANT",
                        },
                        "amount": {
                            "currency_code": "USD",
                            "value": "40.00",
                        },
                    }
                ],
            },
        )

    paypal, http = make_client(handler)

    async with http:
        with pytest.raises(
            PayPalSandboxError,
            match="merchant mismatch",
        ):
            await paypal.create_order(
                amount=Decimal("40.00"),
                currency="USD",
                provider_idempotency_key="intentra-merchant-check",
                expected_paypal_merchant_id="EXPECTED_MERCHANT",
            )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "merchant,amount,currency",
    [
        ("WRONG_MERCHANT", "40.00", "USD"),
        ("TEST_MERCHANT", "90.00", "USD"),
        ("TEST_MERCHANT", "40.00", "CAD"),
    ],
)
async def test_paypal_lookup_rejects_mismatched_order(
    merchant,
    amount,
    currency,
):
    def handler(request):
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(
                200,
                json={"access_token": "mock-token"},
            )

        return httpx.Response(
            200,
            json={
                "id": "MOCK-LOOKUP-123",
                "status": "CREATED",
                "purchase_units": [
                    {
                        "payee": {"merchant_id": merchant},
                        "amount": {
                            "currency_code": currency,
                            "value": amount,
                        },
                    }
                ],
            },
        )

    paypal, http = make_client(handler)

    async with http:
        with pytest.raises(PayPalSandboxError):
            await paypal.get_order(
                order_id="MOCK-LOOKUP-123",
                expected_paypal_merchant_id="TEST_MERCHANT",
                amount=Decimal("40.00"),
                currency="USD",
            )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"id": "WRONG-ORDER"},
        {"id": "MOCK-LOOKUP-123", "purchase_units": []},
        {
            "id": "MOCK-LOOKUP-123",
            "purchase_units": [
                {
                    "payee": {"merchant_id": "TEST_MERCHANT"},
                    "amount": {
                        "currency_code": "USD",
                        "value": "not-a-number",
                    },
                }
            ],
        },
    ],
)
async def test_paypal_lookup_rejects_malformed_order(payload):
    def handler(request):
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(
                200,
                json={"access_token": "mock-token"},
            )

        return httpx.Response(200, json=payload)

    paypal, http = make_client(handler)

    async with http:
        with pytest.raises(PayPalSandboxError):
            await paypal.get_order(
                order_id="MOCK-LOOKUP-123",
                expected_paypal_merchant_id="TEST_MERCHANT",
                amount=Decimal("40.00"),
                currency="USD",
            )


@pytest.mark.asyncio
async def test_paypal_lookup_timeout_is_not_payment_failure():
    def handler(request):
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(
                200,
                json={"access_token": "mock-token"},
            )

        raise httpx.ReadTimeout("Simulated lookup timeout")

    paypal, http = make_client(handler)

    async with http:
        with pytest.raises(PayPalSandboxError):
            await paypal.get_order(
                order_id="MOCK-LOOKUP-123",
                expected_paypal_merchant_id="TEST_MERCHANT",
                amount=Decimal("40.00"),
                currency="USD",
            )
