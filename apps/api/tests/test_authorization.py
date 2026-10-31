from decimal import Decimal

import pytest

from intentra.services.authorization import (
    Decision,
    IntentContract,
    PaymentProposal,
    authorize,
)


@pytest.fixture
def contract():
    return IntentContract(
        merchant_id="merchant-123",
        maximum_amount=Decimal("200.00"),
        currency="USD",
        approved=True,
    )


def test_valid_payment(contract):
    proposal = PaymentProposal(
        merchant_id="merchant-123",
        amount=Decimal("150.00"),
        currency="USD",
    )

    result = authorize(contract, proposal)

    assert result.decision == Decision.ALLOW


def test_budget_exceeded(contract):
    proposal = PaymentProposal(
        merchant_id="merchant-123",
        amount=Decimal("250.00"),
        currency="USD",
    )

    result = authorize(contract, proposal)

    assert result.decision == Decision.BLOCK


def test_merchant_substitution(contract):
    proposal = PaymentProposal(
        merchant_id="attacker-merchant",
        amount=Decimal("100.00"),
        currency="USD",
    )

    result = authorize(contract, proposal)

    assert result.decision == Decision.BLOCK


def test_currency_mismatch(contract):
    proposal = PaymentProposal(
        merchant_id="merchant-123",
        amount=Decimal("100.00"),
        currency="EUR",
    )

    result = authorize(contract, proposal)

    assert result.decision == Decision.BLOCK


def test_unapproved_contract(contract):
    unapproved = IntentContract(
        merchant_id=contract.merchant_id,
        maximum_amount=contract.maximum_amount,
        currency=contract.currency,
        approved=False,
    )

    proposal = PaymentProposal(
        merchant_id="merchant-123",
        amount=Decimal("100.00"),
        currency="USD",
    )

    result = authorize(unapproved, proposal)

    assert result.decision == Decision.BLOCK


@pytest.mark.parametrize(
    "amount",
    [
        Decimal("0"),
        Decimal("-10"),
        Decimal("NaN"),
        Decimal("Infinity"),
    ],
)
def test_invalid_payment_amounts(contract, amount):
    proposal = PaymentProposal(
        merchant_id="merchant-123",
        amount=amount,
        currency="USD",
    )

    result = authorize(contract, proposal)

    assert result.decision == Decision.BLOCK
