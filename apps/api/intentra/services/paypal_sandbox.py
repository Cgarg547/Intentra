import base64
from dataclasses import dataclass
from decimal import Decimal

import httpx


SANDBOX_BASE_URL = "https://api-m.sandbox.paypal.com"
PAYPAL_HTTP_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


class PayPalSandboxError(Exception):
    pass


@dataclass(frozen=True)
class PayPalSandboxConfig:
    client_id: str
    client_secret: str


def validate_paypal_order(
    data: dict,
    *,
    order_id: str | None,
    expected_paypal_merchant_id: str,
    amount: Decimal,
    currency: str,
) -> None:
    """Verify the identity and authorized payment details of an order."""
    if (
        not isinstance(data, dict)
        or not isinstance(data.get("id"), str)
        or not data["id"].strip()
        or (order_id is not None and data["id"] != order_id)
    ):
        raise PayPalSandboxError("PayPal returned an invalid order.")

    purchase_units = data.get("purchase_units")

    if (
        not isinstance(purchase_units, list)
        or len(purchase_units) != 1
        or not isinstance(purchase_units[0], dict)
    ):
        raise PayPalSandboxError(
            "PayPal returned an invalid purchase unit."
        )

    payee = purchase_units[0].get("payee")

    if (
        not isinstance(payee, dict)
        or payee.get("merchant_id") != expected_paypal_merchant_id
    ):
        raise PayPalSandboxError("PayPal order merchant mismatch.")

    order_amount = purchase_units[0].get("amount")

    if not isinstance(order_amount, dict):
        raise PayPalSandboxError(
            "PayPal returned an invalid order amount."
        )

    if order_amount.get("currency_code") != currency:
        raise PayPalSandboxError("PayPal order currency mismatch.")

    raw_value = order_amount.get("value")

    if not isinstance(raw_value, str):
        raise PayPalSandboxError(
            "PayPal returned an invalid order amount."
        )

    try:
        actual_amount = Decimal(raw_value)
    except Exception as exc:
        raise PayPalSandboxError(
            "PayPal returned an invalid order amount."
        ) from exc

    if not actual_amount.is_finite() or actual_amount != amount:
        raise PayPalSandboxError("PayPal order amount mismatch.")


class PayPalSandboxClient:
    def __init__(
        self,
        config: PayPalSandboxConfig,
        *,
        http_client: httpx.AsyncClient,
    ):
        if not config.client_id or not config.client_secret:
            raise PayPalSandboxError("PayPal credentials are missing.")

        self.config = config
        self.http = http_client

    async def get_access_token(self) -> str:
        credentials = (
            f"{self.config.client_id}:{self.config.client_secret}"
        ).encode()

        basic_auth = base64.b64encode(credentials).decode()

        response = await self.http.post(
            f"{SANDBOX_BASE_URL}/v1/oauth2/token",
            headers={
                "Authorization": f"Basic {basic_auth}",
                "Accept": "application/json",
            },
            data={"grant_type": "client_credentials"},
            timeout=PAYPAL_HTTP_TIMEOUT,
        )

        if response.status_code != 200:
            raise PayPalSandboxError(
                f"PayPal authentication failed: HTTP {response.status_code}"
            )

        token = response.json().get("access_token")

        if not isinstance(token, str) or not token:
            raise PayPalSandboxError(
                "PayPal returned an invalid access token."
            )

        return token

    async def create_order(
        self,
        *,
        amount: Decimal,
        currency: str,
        provider_idempotency_key: str,
        expected_paypal_merchant_id: str,
    ) -> dict:
        if not amount.is_finite() or amount <= 0:
            raise PayPalSandboxError("Invalid payment amount.")

        if amount.as_tuple().exponent < -2:
            raise PayPalSandboxError(
                "Payment amount has excessive precision."
            )

        if len(currency) != 3 or not currency.isalpha() or not currency.isupper():
            raise PayPalSandboxError("Invalid currency.")

        if not provider_idempotency_key:
            raise PayPalSandboxError("Missing idempotency key.")

        if (
            not isinstance(expected_paypal_merchant_id, str)
            or not expected_paypal_merchant_id.strip()
        ):
            raise PayPalSandboxError(
                "Missing verified PayPal merchant ID."
            )

        token = await self.get_access_token()

        try:
            response = await self.http.post(
                f"{SANDBOX_BASE_URL}/v2/checkout/orders",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "PayPal-Request-Id": provider_idempotency_key,
                },
                timeout=PAYPAL_HTTP_TIMEOUT,
                json={
                    "intent": "CAPTURE",
                    "purchase_units": [
                        {
                            "payee": {
                                "merchant_id": expected_paypal_merchant_id,
                            },
                            "amount": {
                                "currency_code": currency,
                                "value": f"{amount:.2f}",
                            },
                        }
                    ],
                },
            )
        except httpx.RequestError as exc:
            raise PayPalSandboxError(
                "PayPal order creation outcome unknown; "
                "reconcile using the original idempotency key."
            ) from exc

        if response.status_code not in (200, 201):
            raise PayPalSandboxError(
                "PayPal order creation outcome unknown; "
                f"provider returned HTTP {response.status_code}. "
                "Reconcile using the original idempotency key."
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise PayPalSandboxError(
                "PayPal order creation outcome unknown; "
                "provider returned an unreadable response. "
                "Reconcile using the original idempotency key."
            ) from exc

        validate_paypal_order(
            data,
            order_id=None,
            expected_paypal_merchant_id=expected_paypal_merchant_id,
            amount=amount,
            currency=currency,
        )

        return data

    async def get_order(
        self,
        *,
        order_id: str,
        expected_paypal_merchant_id: str,
        amount: Decimal,
        currency: str,
    ) -> dict:
        """
        Retrieve and verify an existing PayPal order.

        Does not create an order, capture payment, or
        establish that a payment was completed.
        """
        if (
            not isinstance(order_id, str)
            or not order_id.strip()
            or order_id != order_id.strip()
            or len(order_id) > 128
            or "/" in order_id
            or "?" in order_id
            or "#" in order_id
        ):
            raise PayPalSandboxError("Invalid PayPal order ID.")

        if (
            not isinstance(expected_paypal_merchant_id, str)
            or not expected_paypal_merchant_id.strip()
        ):
            raise PayPalSandboxError(
                "Missing verified PayPal merchant ID."
            )

        if (
            not isinstance(amount, Decimal)
            or not amount.is_finite()
            or amount <= 0
        ):
            raise PayPalSandboxError("Invalid expected payment amount.")

        if (
            not isinstance(currency, str)
            or len(currency) != 3
            or not currency.isalpha()
            or not currency.isupper()
        ):
            raise PayPalSandboxError("Invalid expected currency.")

        token = await self.get_access_token()

        try:
            response = await self.http.get(
                f"{SANDBOX_BASE_URL}/v2/checkout/orders/{order_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=PAYPAL_HTTP_TIMEOUT,
            )
        except httpx.RequestError as exc:
            raise PayPalSandboxError(
                "PayPal order lookup failed; payment state remains unknown."
            ) from exc

        if response.status_code != 200:
            raise PayPalSandboxError(
                "PayPal order lookup failed; "
                f"provider returned HTTP {response.status_code}. "
                "Payment state remains unknown."
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise PayPalSandboxError(
                "PayPal returned an unreadable order response."
            ) from exc

        validate_paypal_order(
            data,
            order_id=order_id,
            expected_paypal_merchant_id=expected_paypal_merchant_id,
            amount=amount,
            currency=currency,
        )

        return data
