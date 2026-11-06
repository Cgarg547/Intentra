import base64
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re
from urllib.parse import urlsplit

import httpx


SANDBOX_BASE_URL = "https://api-m.sandbox.paypal.com"
PAYPAL_HTTP_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


def _valid_paypal_order_id(order_id: object) -> bool:
    """Accept only IDs that are safe to persist and later place in an order URL."""
    return (
        isinstance(order_id, str)
        and bool(order_id.strip())
        and order_id == order_id.strip()
        and len(order_id) <= 128
        and "/" not in order_id
        and "?" not in order_id
        and "#" not in order_id
        and all(ord(character) >= 32 and ord(character) != 127 for character in order_id)
    )


class PayPalSandboxError(Exception):
    pass


class PayPalOrderNotSubmittedError(PayPalSandboxError):
    """Order creation did not reach the Orders API."""


class PayPalOrderRejectedError(PayPalSandboxError):
    """The Orders API definitively rejected the create request."""

    def __init__(self, status_code: int):
        self.status_code = status_code
        super().__init__(f"PayPal rejected order creation with HTTP {status_code}.")


class PayPalOrderOutcomeUnknownError(PayPalSandboxError):
    """The create request may have been accepted; never issue a new key."""

    def __init__(self, message: str, *, status_code: int | None = None):
        self.status_code = status_code
        super().__init__(message)


class PayPalCaptureNotSubmittedError(PayPalSandboxError):
    """Authentication failed before the capture request was submitted."""


class PayPalCaptureOutcomeUnknownError(PayPalSandboxError):
    """The capture may have reached PayPal; reconcile before any retry."""


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
        or not _valid_paypal_order_id(data.get("id"))
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
    except InvalidOperation as exc:
        raise PayPalSandboxError(
            "PayPal returned an invalid order amount."
        ) from exc

    if not actual_amount.is_finite() or actual_amount.as_tuple().exponent < -2 or actual_amount != amount:
        raise PayPalSandboxError("PayPal order amount mismatch.")


def validate_paypal_capture(
    data: dict,
    *,
    order_id: str,
    expected_paypal_merchant_id: str,
    amount: Decimal,
    currency: str,
) -> str:
    """Validate capture response identity and its single capture resource."""
    validate_paypal_order(
        data,
        order_id=order_id,
        expected_paypal_merchant_id=expected_paypal_merchant_id,
        amount=amount,
        currency=currency,
    )

    purchase_units = data.get("purchase_units")
    if not isinstance(purchase_units, list) or len(purchase_units) != 1:
        raise PayPalSandboxError("PayPal returned an invalid capture response.")
    purchase_unit = purchase_units[0]
    if not isinstance(purchase_unit, dict):
        raise PayPalSandboxError("PayPal returned an invalid capture response.")
    payments = purchase_unit.get("payments")
    captures = payments.get("captures") if isinstance(payments, dict) else None
    if not isinstance(captures, list) or len(captures) != 1:
        raise PayPalSandboxError("PayPal returned an invalid capture response.")

    capture = captures[0]
    if not isinstance(capture, dict):
        raise PayPalSandboxError("PayPal returned an invalid capture response.")

    capture_id = capture.get("id")
    status = capture.get("status")
    if (
        not isinstance(capture_id, str)
        or not capture_id.strip()
        or capture_id != capture_id.strip()
        or len(capture_id) > 128
        or not isinstance(status, str)
        or status not in {"COMPLETED", "PENDING", "DECLINED", "FAILED"}
    ):
        raise PayPalSandboxError("PayPal returned an invalid capture identity or status.")

    capture_amount = capture.get("amount")
    if not isinstance(capture_amount, dict):
        raise PayPalSandboxError("PayPal returned an invalid capture amount.")
    if capture_amount.get("currency_code") != currency:
        raise PayPalSandboxError("PayPal capture currency mismatch.")
    raw_value = capture_amount.get("value")
    try:
        captured_amount = Decimal(raw_value) if isinstance(raw_value, str) else None
    except InvalidOperation as exc:
        raise PayPalSandboxError("PayPal returned an invalid capture amount.") from exc
    if captured_amount is None or not captured_amount.is_finite() or captured_amount.as_tuple().exponent < -2 or captured_amount != amount:
        raise PayPalSandboxError("PayPal capture amount mismatch.")

    return status


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

        try:
            response = await self.http.post(
                f"{SANDBOX_BASE_URL}/v1/oauth2/token",
                headers={
                    "Authorization": f"Basic {basic_auth}",
                    "Accept": "application/json",
                },
                data={"grant_type": "client_credentials"},
                timeout=PAYPAL_HTTP_TIMEOUT,
            )
        except httpx.RequestError as exc:
            raise PayPalSandboxError("PayPal authentication request failed.") from exc

        if response.status_code != 200:
            raise PayPalSandboxError(
                f"PayPal authentication failed: HTTP {response.status_code}"
            )

        try:
            token_payload = response.json()
        except ValueError as exc:
            raise PayPalSandboxError("PayPal returned an invalid authentication response.") from exc
        token = token_payload.get("access_token") if isinstance(token_payload, dict) else None

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
        return_url: str | None = None,
        cancel_url: str | None = None,
    ) -> dict:
        if not amount.is_finite() or amount <= 0:
            raise PayPalOrderNotSubmittedError("Invalid payment amount.")

        if amount.as_tuple().exponent < -2:
            raise PayPalOrderNotSubmittedError(
                "Payment amount has excessive precision."
            )

        if not isinstance(currency, str) or not re.fullmatch(r"[A-Z]{3}", currency):
            raise PayPalOrderNotSubmittedError("Invalid currency.")

        if not provider_idempotency_key:
            raise PayPalOrderNotSubmittedError("Missing idempotency key.")

        if (
            not isinstance(expected_paypal_merchant_id, str)
            or not expected_paypal_merchant_id.strip()
        ):
            raise PayPalOrderNotSubmittedError(
                "Missing verified PayPal merchant ID."
            )

        try:
            token = await self.get_access_token()
        except PayPalSandboxError as exc:
            raise PayPalOrderNotSubmittedError(
                "PayPal order request was not submitted because authentication failed."
            ) from exc

        paypal_request = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "payee": {"merchant_id": expected_paypal_merchant_id},
                    "amount": {
                        "currency_code": currency,
                        "value": f"{amount:.2f}",
                    },
                }
            ],
        }
        if return_url is not None or cancel_url is not None:
            if not isinstance(return_url, str) or not isinstance(cancel_url, str):
                raise PayPalOrderNotSubmittedError("Both PayPal return URLs are required.")
            return_parts, cancel_parts = urlsplit(return_url), urlsplit(cancel_url)
            valid_return = (return_parts.scheme == "https" or
                (return_parts.scheme == "http" and return_parts.hostname in {"localhost", "127.0.0.1"}))
            valid_cancel = (cancel_parts.scheme == "https" or
                (cancel_parts.scheme == "http" and cancel_parts.hostname in {"localhost", "127.0.0.1"}))
            if (not valid_return or not valid_cancel or not return_parts.netloc or
                not cancel_parts.netloc or return_parts.netloc != cancel_parts.netloc or
                return_parts.username is not None or return_parts.password is not None or
                cancel_parts.username is not None or cancel_parts.password is not None or
                return_parts.fragment or cancel_parts.fragment):
                raise PayPalOrderNotSubmittedError("Invalid PayPal return URLs.")
            paypal_request["payment_source"] = {
                "paypal": {"experience_context": {
                    "return_url": return_url,
                    "cancel_url": cancel_url,
                }}
            }

        try:
            response = await self.http.post(
                f"{SANDBOX_BASE_URL}/v2/checkout/orders",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "PayPal-Request-Id": provider_idempotency_key,
                },
                timeout=PAYPAL_HTTP_TIMEOUT,
                json=paypal_request,
            )
        except httpx.RequestError as exc:
            raise PayPalOrderOutcomeUnknownError(
                "PayPal order creation outcome unknown after submission."
            ) from exc

        if response.status_code not in (200, 201):
            if response.status_code in {400, 401, 403, 404, 422}:
                raise PayPalOrderRejectedError(response.status_code)
            raise PayPalOrderOutcomeUnknownError(
                f"PayPal order creation outcome unknown (HTTP {response.status_code}).",
                status_code=response.status_code,
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise PayPalOrderOutcomeUnknownError(
                "PayPal order creation outcome unknown; provider returned an unreadable response.",
                status_code=response.status_code,
            ) from exc

        try:
            validate_paypal_order(
                data,
                order_id=None,
                expected_paypal_merchant_id=expected_paypal_merchant_id,
                amount=amount,
                currency=currency,
            )
        except PayPalSandboxError as exc:
            # A 2xx response may already have created an order. Invalid
            # evidence must therefore block automatic create retries.
            raise PayPalOrderOutcomeUnknownError(
                f"PayPal order creation outcome unknown; {exc}",
                status_code=response.status_code,
            ) from exc

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
        if not _valid_paypal_order_id(order_id):
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
            or not re.fullmatch(r"[A-Z]{3}", currency)
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

    async def capture_order(
        self,
        *,
        order_id: str,
        expected_paypal_merchant_id: str,
        amount: Decimal,
        currency: str,
        provider_idempotency_key: str,
    ) -> dict:
        """Capture a buyer-approved order; callers must interpret its validated status."""
        if (
            not isinstance(order_id, str)
            or not order_id.strip()
            or order_id != order_id.strip()
            or len(order_id) > 128
            or any(char in order_id for char in "/?#")
        ):
            raise PayPalSandboxError("Invalid PayPal order ID.")
        if (
            not isinstance(amount, Decimal)
            or not amount.is_finite()
            or amount <= 0
            or amount.as_tuple().exponent < -2
        ):
            raise PayPalSandboxError("Invalid expected payment amount.")
        if (
            not isinstance(currency, str)
            or not re.fullmatch(r"[A-Z]{3}", currency)
        ):
            raise PayPalSandboxError("Invalid expected currency.")
        if (
            not isinstance(provider_idempotency_key, str)
            or not provider_idempotency_key.strip()
            or len(provider_idempotency_key) > 108
            or not provider_idempotency_key.isascii()
            or not re.fullmatch(r"[A-Za-z0-9]+", provider_idempotency_key)
        ):
            raise PayPalSandboxError("Invalid capture idempotency key.")
        if (
            not isinstance(expected_paypal_merchant_id, str)
            or not expected_paypal_merchant_id.strip()
        ):
            raise PayPalSandboxError("Missing verified PayPal merchant ID.")

        try:
            token = await self.get_access_token()
        except Exception as exc:
            # No capture request is sent until authentication succeeds.
            raise PayPalCaptureNotSubmittedError(
                "PayPal authentication failed before capture submission."
            ) from exc
        try:
            response = await self.http.post(
                f"{SANDBOX_BASE_URL}/v2/checkout/orders/{order_id}/capture",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "PayPal-Request-Id": provider_idempotency_key,
                },
                timeout=PAYPAL_HTTP_TIMEOUT,
                json={},
            )
        except httpx.RequestError as exc:
            raise PayPalCaptureOutcomeUnknownError(
                "PayPal capture outcome unknown; reconcile the existing order before retrying."
            ) from exc

        if response.status_code not in (200, 201):
            raise PayPalCaptureOutcomeUnknownError(
                "PayPal capture outcome unknown; "
                f"provider returned HTTP {response.status_code}. "
                "Retrieve and reconcile the existing order before retrying."
            )
        try:
            data = response.json()
        except ValueError as exc:
            raise PayPalCaptureOutcomeUnknownError(
                "PayPal capture outcome unknown; provider returned unreadable data."
            ) from exc

        try:
            validate_paypal_capture(
                data,
                order_id=order_id,
                expected_paypal_merchant_id=expected_paypal_merchant_id,
                amount=amount,
                currency=currency,
            )
        except PayPalSandboxError as exc:
            raise PayPalCaptureOutcomeUnknownError(
                "PayPal capture response could not be verified; reconciliation is required."
            ) from exc
        return data
