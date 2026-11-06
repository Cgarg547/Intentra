from decimal import Decimal

import pytest

from intentra.services.agent_provider import (
    AgentProviderError,
    ExtractedPurchase,
    MockPurchasePlanningProvider,
    validate_extraction_evidence,
)


REQUEST = """Purchase purpose: Digital productivity template.
Merchant ID: paypal_merchant_demo.
Purchase amount: 0.01.
Currency: USD.
This is a synthetic PayPal Sandbox demonstration."""


@pytest.mark.asyncio
async def test_labeled_purchase_extraction():
    result = await MockPurchasePlanningProvider().extract(REQUEST)

    assert result.purpose == "Digital productivity template."
    assert result.merchant_id == "paypal_merchant_demo"
    assert result.amount == Decimal("0.01")
    assert result.currency == "USD"


def test_invented_amount_is_rejected():
    extraction = ExtractedPurchase(
        purpose="Digital productivity template.",
        merchant_id="paypal_merchant_demo",
        amount=Decimal("99.00"),
        currency="USD",
    )

    with pytest.raises(AgentProviderError) as error:
        validate_extraction_evidence(REQUEST, extraction)

    assert error.value.code == "OPENAI_INVALID_RESPONSE"


def test_invented_currency_is_rejected():
    extraction = ExtractedPurchase(
        purpose="Digital productivity template.",
        merchant_id="paypal_merchant_demo",
        amount=Decimal("0.01"),
        currency="EUR",
    )

    with pytest.raises(AgentProviderError) as error:
        validate_extraction_evidence(REQUEST, extraction)

    assert error.value.code == "OPENAI_INVALID_RESPONSE"


def test_invented_merchant_is_rejected():
    extraction = ExtractedPurchase(
        purpose="Digital productivity template.",
        merchant_id="unknown_merchant",
        amount=Decimal("0.01"),
        currency="USD",
    )

    with pytest.raises(AgentProviderError) as error:
        validate_extraction_evidence(REQUEST, extraction)

    assert error.value.code == "OPENAI_INVALID_RESPONSE"
