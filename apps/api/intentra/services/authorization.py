from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class Decision(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    REVIEW = "REVIEW"


@dataclass(frozen=True)
class IntentContract:
    merchant_id: str
    maximum_amount: Decimal
    currency: str
    approved: bool


@dataclass(frozen=True)
class PaymentProposal:
    merchant_id: str
    amount: Decimal
    currency: str


@dataclass(frozen=True)
class AuthorizationResult:
    decision: Decision
    reason: str


def authorize(
    contract: IntentContract,
    proposal: PaymentProposal,
) -> AuthorizationResult:

    if not contract.approved:
        return AuthorizationResult(
            Decision.BLOCK,
            "Intent contract has not been approved.",
        )

    if not contract.merchant_id or not proposal.merchant_id:
        return AuthorizationResult(
            Decision.BLOCK,
            "Merchant identifier is missing.",
        )

    if contract.merchant_id != proposal.merchant_id:
        return AuthorizationResult(
            Decision.BLOCK,
            "Merchant does not match the authorized merchant.",
        )

    if contract.currency != proposal.currency:
        return AuthorizationResult(
            Decision.BLOCK,
            "Payment currency does not match the contract.",
        )

    if (
        not contract.maximum_amount.is_finite()
        or not proposal.amount.is_finite()
        or contract.maximum_amount <= 0
        or proposal.amount <= 0
    ):
        return AuthorizationResult(
            Decision.BLOCK,
            "Payment amount or spending limit is invalid.",
        )

    if proposal.amount > contract.maximum_amount:
        return AuthorizationResult(
            Decision.BLOCK,
            "Payment exceeds the authorized spending limit.",
        )

    return AuthorizationResult(
        Decision.ALLOW,
        "Payment matches the approved intent contract.",
    )
