from dataclasses import dataclass
import json
import os
from types import MappingProxyType
from typing import Mapping


class MerchantRegistryError(Exception):
    pass


@dataclass(frozen=True)
class VerifiedMerchant:
    internal_merchant_id: str
    paypal_merchant_id: str


class TrustedMerchantRegistry:
    """
    Server-controlled mapping of internal merchant IDs
    to verified PayPal merchant account IDs.

    Never populate this mapping from an AI proposal,
    a payment request, or unverified user input.
    """

    def __init__(self, mappings: Mapping[str, str]):
        verified = {}

        for internal_id, paypal_id in mappings.items():
            if (
                not isinstance(internal_id, str)
                or not internal_id.strip()
                or internal_id != internal_id.strip()
                or len(internal_id) > 128
            ):
                raise MerchantRegistryError(
                    "Invalid internal merchant ID."
                )

            if (
                not isinstance(paypal_id, str)
                or not paypal_id.strip()
                or paypal_id != paypal_id.strip()
                or len(paypal_id) > 128
            ):
                raise MerchantRegistryError(
                    "Invalid PayPal merchant ID."
                )

            verified[internal_id] = paypal_id

        if len(set(verified.values())) != len(verified):
            raise MerchantRegistryError(
                "Multiple internal merchants share a PayPal account."
            )

        self._mappings = MappingProxyType(verified)

    def resolve(self, internal_merchant_id: str) -> VerifiedMerchant:
        if (
            not isinstance(internal_merchant_id, str)
            or internal_merchant_id not in self._mappings
        ):
            raise MerchantRegistryError(
                "Merchant is not registered for PayPal."
            )

        return VerifiedMerchant(
            internal_merchant_id=internal_merchant_id,
            paypal_merchant_id=self._mappings[internal_merchant_id],
        )

    def verified_mappings(self) -> tuple[VerifiedMerchant, ...]:
        """Return immutable server-configured identities for authenticated views."""
        return tuple(VerifiedMerchant(internal_id, paypal_id)
                     for internal_id, paypal_id in sorted(self._mappings.items()))


def load_trusted_merchant_registry() -> TrustedMerchantRegistry | None:
    """Load only the trusted internal-to-provider identity map; never credentials."""
    raw = os.getenv("PAYPAL_SANDBOX_MERCHANTS")
    if not raw:
        return None
    try:
        mappings = json.loads(raw)
        if not isinstance(mappings, dict):
            raise ValueError
        return TrustedMerchantRegistry(mappings)
    except (json.JSONDecodeError, ValueError, TypeError, MerchantRegistryError):
        raise MerchantRegistryError("Trusted merchant registry is unavailable.") from None
