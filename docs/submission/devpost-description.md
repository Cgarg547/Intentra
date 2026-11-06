# INTENTRA — Devpost description draft

**Title:** INTENTRA
**Tagline:** Human-governed payments for AI agents.

## Problem

AI can turn a natural-language purchasing request into structured data quickly,
but it should not silently choose a merchant, approve a budget, or execute a
payment. Teams need human accountability when an AI assistant helps prepare a
purchase.

## Solution

## Human-governed payments for AI agents

INTENTRA helps a procurement or operations team turn an AI-assisted purchase
request into a controlled payment workflow. It is built for teams that want AI
speed without letting an AI model silently spend money.

An agent extracts structured facts from an explicit request using a local Ollama
model. INTENTRA then evaluates deterministic owner-scoped policy: approved
contract, merchant, currency, amount, budget and version. A person must review
and confirm an allowed proposal before a reservation and payment attempt can be
prepared. PayPal Sandbox checkout and capture are separate, verified steps; the
browser success screen is never treated as payment truth.

## What is innovative

The model is deliberately not the authorization authority. INTENTRA separates
untrusted AI extraction from deterministic policy, explicit human confirmation,
durable idempotency, merchant/payee validation and provider-outcome
reconciliation. If a provider response is ambiguous, the budget stays held and
the existing attempt must be reconciled—there is no blind order or capture retry.

## Technical implementation

- Next.js 16 / React 19 workspace for contracts, agents, approvals, payments,
  analytics and audit exploration.
- FastAPI, PostgreSQL and Alembic for owner-scoped records and append-only audit
  events.
- Local Ollama with `qwen3:4b` for bounded structured extraction; mock mode is
  available for offline demonstration and is labeled as such.
- Direct PayPal Sandbox REST Orders integration with server-side order and
  capture validation, one-time checkout return state, and durable request IDs.

## Sponsor integration

INTENTRA integrates directly with **PayPal Sandbox Orders v2**. The server keeps
Sandbox credentials and merchant mappings off the client, creates and retrieves
orders only after deterministic policy and human confirmation, validates the
server-observed payee/amount/currency, and performs capture as a separate
one-time claimed operation. This is a Sandbox implementation, not a claim that
a live or real-money transaction occurred.

## Impact and limitations

INTENTRA demonstrates a safer pattern for AI-assisted purchasing: humans and
policy remain accountable while AI reduces request-handling friction. This is a
local prototype, not a bank, product-discovery engine, or autonomous checkout
service. It does not claim savings, revenue, merchant verification or live
provider success without corresponding evidence. A full Sandbox journey,
including buyer approval and a separately authorized capture, is only shown when
the recording labels it as PayPal Sandbox and includes the resulting audit trail.

## Submission disclosures

- **Mock:** Offline/mock extraction and intercepted browser tests demonstrate UI
  and deterministic workflow behavior only. They are visibly labeled and are not
  payment-provider evidence.
- **Local Ollama:** When separately enabled, local Ollama `qwen3:4b` extracts
  facts from explicit text. It does not discover products or authorize spend.
- **PayPal Sandbox:** OAuth, order creation, buyer approval, return validation,
  capture and reconciliation require owner approval and dedicated Sandbox
  credentials. Do not claim this proof unless the recording contains the
  corresponding redacted, server-verified audit evidence.
