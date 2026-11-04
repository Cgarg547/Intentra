"""Lazy PayPal Sandbox configuration; no provider calls at startup."""

import json
import os

import httpx

from intentra.services.merchant_registry import TrustedMerchantRegistry
from intentra.services.paypal_sandbox import PayPalSandboxClient, PayPalSandboxConfig


class ProviderConfigurationError(Exception):
    pass


def build_checkout_providers():
    client_id = os.getenv("PAYPAL_SANDBOX_CLIENT_ID")
    client_secret = os.getenv("PAYPAL_SANDBOX_CLIENT_SECRET")
    raw_mappings = os.getenv("PAYPAL_SANDBOX_MERCHANTS")
    if not client_id or not client_secret or not raw_mappings:
        raise ProviderConfigurationError
    try:
        mappings = json.loads(raw_mappings)
        if not isinstance(mappings, dict):
            raise ValueError
        registry = TrustedMerchantRegistry(mappings)
    except (ValueError, TypeError) as exc:
        raise ProviderConfigurationError from exc
    http = httpx.AsyncClient(base_url="https://api-m.sandbox.paypal.com")
    return registry, PayPalSandboxClient(
        PayPalSandboxConfig(client_id, client_secret), http_client=http,
    ), http
