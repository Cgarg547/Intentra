import pytest

from intentra.services.merchant_registry import (
    MerchantRegistryError,
    TrustedMerchantRegistry,
)


def test_registered_merchant_resolves_to_paypal_account():
    registry = TrustedMerchantRegistry(
        {"approved_store": "PAYPAL_ACCOUNT_123"}
    )

    merchant = registry.resolve("approved_store")

    assert merchant.internal_merchant_id == "approved_store"
    assert merchant.paypal_merchant_id == "PAYPAL_ACCOUNT_123"


def test_unknown_merchant_is_rejected():
    registry = TrustedMerchantRegistry(
        {"approved_store": "PAYPAL_ACCOUNT_123"}
    )

    with pytest.raises(
        MerchantRegistryError,
        match="not registered",
    ):
        registry.resolve("attacker_store")


def test_registry_does_not_follow_external_mapping_changes():
    mappings = {"approved_store": "PAYPAL_ACCOUNT_123"}
    registry = TrustedMerchantRegistry(mappings)

    mappings["approved_store"] = "ATTACKER_ACCOUNT"

    assert (
        registry.resolve("approved_store").paypal_merchant_id
        == "PAYPAL_ACCOUNT_123"
    )


@pytest.mark.parametrize(
    "mappings",
    [
        {"": "PAYPAL_ACCOUNT_123"},
        {" approved_store": "PAYPAL_ACCOUNT_123"},
        {"approved_store": ""},
        {"approved_store": " PAYPAL_ACCOUNT_123"},
        {"approved_store": "X" * 129},
        {
            "store_a": "SAME_PAYPAL_ACCOUNT",
            "store_b": "SAME_PAYPAL_ACCOUNT",
        },
    ],
)
def test_invalid_registry_configuration_is_rejected(mappings):
    with pytest.raises(MerchantRegistryError):
        TrustedMerchantRegistry(mappings)


def test_registry_does_not_expose_mutable_mapping():
    registry = TrustedMerchantRegistry(
        {"approved_store": "PAYPAL_ACCOUNT_123"}
    )

    with pytest.raises(TypeError):
        registry._mappings["approved_store"] = "ATTACKER_ACCOUNT"
