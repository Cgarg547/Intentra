# PayPal Sandbox demo runbook

This runbook prepares one connected AI-to-PayPal **Sandbox** demonstration. It
does not authorize its execution. No credential, API request, order, buyer
approval, capture, reservation, database write, migration, service restart, or
deployment was performed while creating this document.

## Scope and stop rule

The only proposed transaction is one synthetic purchase of **USD 0.01** through
one dedicated Sandbox buyer and one dedicated Sandbox business merchant. The
amount is the smallest positive two-decimal amount accepted by INTENTRA's money
validation. If the selected Sandbox account/currency rejects it, stop and record
the provider rejection; do not increase the amount, create another order, or
retry automatically.

Stop immediately if any identity, amount, currency, contract version, approval
state, expected order ID, or provider response cannot be verified. An uncertain
provider result is not a failed payment and is never an authorization to retry.

## Connected workflow trace

| Stage | Existing route/service | Required input | Expected durable state / audit evidence | Guard | Evidence status |
| --- | --- | --- | --- | --- | --- |
| 1. Authenticated request | `POST /api/agents/proposals`; `routes/agents.py`, `agent_proposals.py` | Authenticated owner, explicit purchase text | Owner-scoped proposal and proposal events | Session/owner checks; model output remains untrusted | Offline + mocked browser verified; live AI must be separately approved |
| 2. Product/merchant selection | `agent_provider.py`; proposal schema | Explicit merchant ID, amount, currency in request/model response | Proposal records structured merchant, purpose, amount, currency | There is no catalog/search/quote adapter; unknown merchant cannot become trusted | Extraction exists; **product discovery is missing** |
| 3. Spending policy | `authorize`; `agent_proposals.py`; `agent_payment_handoff.py` | Current owner contract and proposed amount/currency/merchant | Policy ALLOW/BLOCK evidence; confirmed proposal only if eligible | Approved owner contract, exact merchant/currency, positive amount <= limit, version check | Offline verified |
| 4. Human approval | Proposal confirmation route/service | Explicit owner confirmation of an ALLOW proposal | `CONFIRMED` proposal and handoff provenance | Owner scope, current contract/version, review gate | Mocked browser/offline verified |
| 5. Reservation/preparation | `POST /api/agents/proposals/{id}/prepare-payment`; `agent_payment_handoff.py` | Confirmed eligible proposal and idempotency key | Reservation, pending attempt, handoff, `CHECKOUT_NOT_STARTED` provenance | Transaction locks, owner/contract/version/budget/merchant checks; no provider call here | DB integration tests exist; not run in this no-write workstream |
| 6. PayPal order | `POST /api/payments/reservations/{id}/checkout`; `payment_orchestration.py`, `paypal_sandbox.py` | Eligible reservation, configured server-side Sandbox merchant mapping | `ORDER_CREATE_ATTEMPT_STARTED`, accepted/bound order evidence, one provider order ID/idempotency key | OAuth before submission; exact payee/amount/currency validation; uncertain create blocks new create | Offline adapter verified; live unverified |
| 7. Buyer approval | PayPal-hosted approval URL, then `POST /api/payments/checkout/return`; `checkout_approval.py` | Browser return state, same authenticated owner/session | `CHECKOUT_CREATED`, then `CHECKOUT_APPROVED` with verification timestamp | Hashed one-time state, expiry, consumed state, fresh provider GET, exact identity/amount/currency validation | Offline/mocked verified; live unverified |
| 8. Capture | `POST /api/payments/attempts/{id}/capture`; `payment_capture.py` | Owner, verified unexpired checkout approval | `CAPTURE_CLAIMED`, then terminal capture event or unknown hold | A durable unique capture claim/key is committed before provider call; duplicate calls do not resubmit | Offline verified; live unverified |
| 9. Reconciliation | `POST /api/payments/attempts/{id}/reconcile`; `payment_reconciliation_runner.py` | Existing owner-scoped attempt only | Reconciliation evidence and verified terminal state, or unresolved hold | GET existing order only; no automatic replacement order/capture | Offline verified; live unverified |
| 10. Audit history | Payment/workspace history routes and models | Authenticated owner | Owner-scoped contract, proposal, attempt, approval, capture and reconciliation history | Owner filtering; durable event/evidence records | Offline/mocked verified; live linked evidence missing |

## Preflight checklist

- [ ] Explicit owner approval for the exact test window and USD 0.01 scope.
- [ ] Dedicated, disposable database at Alembic head `9d7f1a4c6b20`; snapshot/backup policy approved.
- [ ] No unresolved existing payment attempt/reservation will be reused.
- [ ] Dedicated PayPal Sandbox REST app, business merchant, and buyer account.
- [ ] Backend secret store supplies nonempty `PAYPAL_SANDBOX_CLIENT_ID`,
  `PAYPAL_SANDBOX_CLIENT_SECRET`, and server-owned
  `PAYPAL_SANDBOX_MERCHANTS`; never print their values.
- [ ] Private local Sandbox config remains regular, current-user-owned, and mode
  `0600`; its values stay out of shell history, screenshots, and logs.
- [ ] One hostname is chosen for the whole flow. The local launcher requires
  `http://localhost:3000`; do not mix it with `127.0.0.1` browser cookies.
- [ ] AI mode is approved: use mocked/deterministic proposal data unless a live
  Ollama extraction has separately been authorized.
- [ ] Browser is a fresh Sandbox-only profile and the screenshot plan is ready.

## Approved-execution sequence

1. Start only the approved services; verify process health without using payment
   endpoints as health checks.
2. Authenticate a synthetic owner. Create and approve one contract for the
   mapped synthetic merchant, USD, limit `0.01`.
3. Create/confirm one exact matching proposal. If live AI is not separately
   approved, use the deterministic/mock route and label it truthfully in media.
4. Prepare exactly one payment. Confirm there is one owner-scoped reservation,
   one pending attempt, and no provider order before checkout launch.
5. Launch checkout once. Record redacted `ORDER_CREATE_*` and
   `CHECKOUT_CREATED` events. Do not reload/retry the launch if the response is
   uncertain.
6. In the dedicated Sandbox buyer profile, approve the order. Return through
   the same host/origin and verify `CHECKOUT_APPROVED` after server-side order
   lookup.
7. With a second explicit approval, capture once. Expect one `CAPTURE_CLAIMED`
   event before the provider request; then expect either `CAPTURE_COMPLETED` and
   `SUCCEEDED`/`CAPTURED`, a definitive failed/cancelled state, or an unknown
   hold requiring reconciliation.
8. Read owner-scoped history and record the final redacted audit chain. Do not
   use a browser success screen as authoritative payment evidence.

## Expected result matrix

| Condition | Expected API/domain result | Expected records | Operator action |
| --- | --- | --- | --- |
| Valid Sandbox completion | Checkout verifies, capture reaches `COMPLETED` | Approved checkout; one capture ID/key; `CAPTURE_COMPLETED`; attempt `SUCCEEDED`; reservation `CAPTURED` | Save redacted evidence and stop. |
| OAuth fails before order/capture submission | Safe unavailable/not-submitted error | No successful provider binding/capture; not-submitted event where applicable | Fix configuration; create no blind retry. |
| Provider create/capture timeout, 5xx, unreadable or invalid evidence | `PROVIDER_OUTCOME_UNKNOWN` / reconciliation-required result | Attempt/reservation remain unknown; outcome event/evidence | Stop; reconcile the existing provider order only after approval. |
| Payee, amount, or currency differs | Validation failure | No terminal success; verification rejection/hold evidence | Stop; investigate mapping/data; do not capture. |
| Return state expired/cancelled/used | Checkout unavailable | `CHECKOUT_EXPIRED` or `CHECKOUT_CANCELLED` | Do not capture; start a new workflow only after review. |
| Duplicate capture request | Existing claim/result returned, no second provider submission | One capture idempotency key/claim | Do not alter state or manually retry. |

## Redacted evidence to retain

Verified Sandbox evidence: the USD 25.00 demonstration reconciled to payment
state `SUCCEEDED`, reservation state `CAPTURED`, and provider status
`COMPLETED`. This is PayPal Sandbox evidence only, never a live-payment claim.

- Build revision, environment label (`Sandbox`), timestamp, and tester role.
- Contract/proposal/reservation/attempt state transitions using internal UUIDs or
  approved short suffixes only.
- Merchant mapping verification result without the full business account ID.
- Amount `USD 0.01`, policy ALLOW, human-confirmation state, provider order
  status, capture status, and reconciliation result.
- Browser screenshot of Sandbox approval with personal details hidden.

Never retain or show client secret, OAuth token, cookie, authorization header,
raw provider request/response, buyer email/name, full merchant account ID, or
unredacted provider IDs.

## Failure handling and recovery

- Do not use `recover_known_paypal_order.py` in the demo. It is a fixed
  historical development-recovery tool pinned to `f1a2b3c4d5e6`, not a
  current-head demo workflow.
- Do not delete/rewrite audit evidence, rotate a request ID, or construct a
  substitute order for an uncertain result.
- For any `UNKNOWN` state, preserve the reservation budget and use the
  owner-scoped reconciliation endpoint only after a separate review decision.
- Revoke/rotate temporary Sandbox credentials after the demo if policy requires.

## Required approvals

This document is preparation only. The next action requiring explicit owner
approval is a read-only Sandbox OAuth preflight (`paypal_sandbox_local.py check`)
with the configured dedicated app. A second approval is required before any
database-writing preparation, order creation, buyer approval, capture, or
reconciliation action.
