# PayPal Sandbox preflight

Assessment date: 2026-11-04. This is a preflight report only. No PayPal request,
OAuth exchange, order, reservation, capture, reconciliation, database write,
migration, service restart, or deployment was performed.

## Decision summary

| Area | Status | Evidence / decision |
| --- | --- | --- |
| Fresh Python installation | PASS | A new disposable Python 3.14.7 virtual environment installed `requirements-dev.txt`, passed `pip check`, and imported the API dependency set. The active `.venv` was not modified. |
| Dependency determinism | PARTIAL | Direct runtime and test dependencies are version pinned in `requirements.txt` / `requirements-dev.txt`; transitive dependencies are resolver-selected and can drift. |
| Documented repository paths | PASS | README commands use `apps/api` for Python/Alembic/tests and `apps/web` for npm; these paths exist. |
| Migration graph | PASS | One linear graph with head `9d7f1a4c6b20`; no migration was executed. |
| Legacy recovery helper | PARTIAL | It is a fixed-context development-recovery tool, not a supported bootstrap or production workflow. Retain only as quarantined legacy tooling pending owner decision. |
| Sandbox configuration shape | PASS | Private configuration exists, is regular/owner-only mode `0600`, parses as JSON, and has nonempty required credential/mapping fields. Values were neither printed nor used. |
| OAuth/Orders v2 adapter | PASS (offline) | OAuth client-credentials, create/get/capture paths, timeout/error handling, and request IDs have code and offline-test evidence. |
| Merchant / amount / currency verification | PASS (offline) | Server-owned merchant map and exact provider-response checks are present and tested. |
| Human approval / duplicate capture | PASS (offline) | Expiring one-time checkout approval plus durable capture claim and unique keys are implemented and tested. |
| Unknown-outcome reconciliation | PASS (offline) | Provider uncertainty holds the reservation and requires lookup/reconciliation rather than retry. |
| Live Sandbox proof | UNKNOWN | Explicitly not performed. |

## Reproducibility findings

### What was verified

The fresh environment was created in a disposable `/private/tmp` directory with
Python 3.14.7, using:

```sh
python3.14 -m venv <temporary>/venv
<temporary>/venv/bin/python -m pip install -r apps/api/requirements-dev.txt
<temporary>/venv/bin/python -m pip check
```

It completed successfully, and imports for FastAPI, SQLAlchemy, asyncpg,
Alembic, HTTPX, Pydantic, password hashing, email validation, pytest, and
pytest-asyncio succeeded. This validates the README's backend install layout
without changing the active application environment.

The initial sandboxed attempt could not resolve PyPI. The approved retry used
the same disposable environment and succeeded. A clean judge installation
therefore still assumes outbound package-registry access (or an organization
provided wheel mirror/cache).

The selected offline runner passed **183 tests in 1.37 seconds**. It sets an
unreachable process-local database URL and blocks socket/DNS operations; its
selected tests do not perform database writes or provider requests.

### Dependency assessment

`requirements.txt` contains observed direct runtime dependencies and
`requirements-dev.txt` adds pytest tooling. This is a good minimal runtime
manifest: it excludes optional local server helpers such as `uvloop`,
`watchfiles`, and `websockets`, all of which Uvicorn can run without. It also
keeps test-only packages out of the runtime file.

It is **not a full lockfile**. Pip resolved newer transitive packages in the
fresh environment than were present in the active virtualenv (for example,
unconstrained transitive packages). For fully byte-for-byte repeatable releases,
generate a hash-locked, platform-aware artifact with pip-tools/uv/Poetry and
store separate macOS/Linux lock outputs or use a pinned wheelhouse. Do not claim
that this direct-dependency manifest guarantees a fully identical transitive
environment.

### Prerequisites and assumptions

- Python 3.14.7 and an available Python package index/mirror.
- Node 22.22.3/npm for the frontend's existing `package-lock.json` and `npm ci`.
- Docker Compose and a free local port 5433 only for separately approved local
  PostgreSQL setup.
- PostgreSQL 17 for migrations/integration tests; no migration or DB connection
  occurred in this preflight.
- A PayPal Developer Sandbox REST app, Sandbox buyer/business accounts, and a
  server-owned mapping from the internal merchant ID to the Sandbox business
  account ID for a later approved demo.
- A planned browser origin: the local Sandbox launcher requires
  `http://localhost:3000`; the normal frontend preview documentation uses
  `127.0.0.1`. Do not mix hostnames during a checkout session.

## Migration safety

The complete verified linear ancestry is:

```text
cff869226bbc → c17b154cbf8d → e652fa5426e5 → 5cb85dc670fb
→ 5a644cf96eec → 8f7b2c41a9d0 → 9c2d7e61b4a0 → b6e91c2a740d
→ c7a42f91e805 → d8f3a91b6c20 → e4b8c12d7a90 → f1a2b3c4d5e6
→ 7a91d4c3e2b0 → 8c4e21a6d9f0 → 9d7f1a4c6b20 (head)
```

`scripts/recover_known_paypal_order.py` has a hard-coded historical attempt,
reservation, contract, provider order, expected amount/currency, and target
revision `f1a2b3c4d5e6`. It requires an explicit
`--confirm-development-recovery` flag and validates the local DB identity before
it performs its narrowly scoped recovery action. It is not invoked by normal
application code or README setup.

**Recommendation: retain as quarantined legacy tooling, not as a supported
workflow.** Do not update only its revision constant: that would weaken a guard
around a fixed historical data context while silently implying compatibility with
later migrations. Before any future use, the owner must either (a) preserve the
historical snapshot matching its guard, or (b) approve a separately designed,
migration-aware, idempotent recovery procedure with tests. It should never be
part of a fresh install, judge demo, or production runbook.

## Configuration checklist

The following checks were performed without printing values. The private
`apps/api/.env.paypal.sandbox.json` is a regular file, owned by the current user
and mode `0600`; its JSON has nonempty:

- `PAYPAL_SANDBOX_CLIENT_ID`
- `PAYPAL_SANDBOX_CLIENT_SECRET`
- `PAYPAL_SANDBOX_MERCHANTS` (nonempty mapping)

Its local launcher origin settings match its strict expected values:

- `INTENTRA_FRONTEND_URL=http://localhost:3000`
- `INTENTRA_ALLOWED_ORIGINS=http://localhost:3000`
- `INTENTRA_API_URL=http://127.0.0.1:8000`

Before a separately approved test, also verify manually that:

- [ ] The REST app is a dedicated **Sandbox** application, not production or a
  shared default credential.
- [ ] The merchant mapping is a server-controlled mapping to the intended
  Sandbox business account; it is not sourced from an AI proposal or browser
  request.
- [ ] The buyer is a distinct Sandbox buyer test account.
- [ ] The test database is a dedicated, disposable database at current head
  `9d7f1a4c6b20` and does not contain personal/production data.
- [ ] No secret is in shell history, frontend environment, logs, screenshots,
  repository, Devpost text, or demo video.
- [ ] The browser session uses only the hostname configured for the callback.

## Payment lifecycle and expected audit evidence

```text
approved, owner-scoped contract
  → policy evaluation / reservation
  → durable payment attempt + ORDER_CREATE_ATTEMPT_STARTED
  → PayPal Orders v2 create (one persisted request ID)
  → validated payee, amount, currency + ORDER_CREATE_PROVIDER_ACCEPTED/BINDING
  → one-time expiring CHECKOUT_CREATED handoff
  → buyer approves in PayPal Sandbox
  → server GETs and validates existing order + CHECKOUT_APPROVED
  → CAPTURE_CLAIMED (state becomes UNKNOWN before external request)
  → capture result: CAPTURE_COMPLETED, CAPTURE_DECLINED/FAILED,
    or CAPTURE_OUTCOME_UNKNOWN
  → uncertain states: provider GET + reconciliation evidence / terminal event
```

The code follows PayPal's documented OAuth client-credentials flow and Sandbox
token endpoint, and uses Orders v2 create, retrieve, and capture operations.
See PayPal's [authentication documentation](https://developer.paypal.com/api/rest/authentication/)
and [Orders v2 reference](https://developer.paypal.com/api/orders/v2/).

Security controls observed in source:

- OAuth uses HTTP Basic credentials only to obtain a bearer token; the code does
  not persist or print the access token.
- Create/capture use distinct durable `PayPal-Request-Id` values.
- `validate_paypal_order` and `validate_paypal_capture` require exactly one
  purchase unit, mapped payee identity, exact decimal amount, and exact
  three-letter currency.
- Checkout approval stores only a hash of a one-time return state, enforces its
  expiry/one-time use, rechecks owner/contract/reservation state, and retrieves
  provider evidence before capture.
- Unique database constraints and a persisted capture claim prevent duplicate
  submission. Provider ambiguity is held as `UNKNOWN`/`OUTCOME_UNKNOWN`; it is
  never released for blind retry.

## Smallest controlled Sandbox test

Use **USD 0.01** for one synthetic purchase, provided the selected Sandbox
buyer/business pair accepts that value. It is the smallest two-decimal positive
amount represented by the current code. Use one unique, plainly synthetic
internal merchant and purpose text; do not represent a real retailer or use
personal details. If Sandbox rejects the amount for the account/currency, stop
and record the rejection; do not automatically raise the amount or retry.

## Exact controlled test plan — requires separate approval

1. Confirm a dedicated Sandbox-only database, browser profile, buyer, business
   account, REST app, origin, and secret injection. Take a backup/snapshot as
   required by the environment owner. This setup may write DB records and is not
   authorized by this preflight.
2. Start only the approved local/deployed services with the configured Sandbox
   environment. Verify `/health` without treating it as payment readiness.
3. Authenticate as the synthetic owner and create/approve a contract for the
   mapped synthetic merchant, USD, maximum `0.01`. Expected DB: contract audit
   events and approved current version.
4. Use the deterministic/mock proposal path or an explicitly approved AI
   proposal whose merchant, amount `0.01`, and currency USD match exactly.
   Expected DB: policy ALLOW evidence and a human-confirmed proposal/handoff.
5. Explicitly prepare one reservation and launch checkout once. Expected API:
   one checkout response/approval URL. Expected DB: one reservation, one payment
   attempt, one create-order idempotency key, `ORDER_CREATE_ATTEMPT_STARTED`,
   accepted/bound order events, and `CHECKOUT_CREATED`.
6. In the isolated Sandbox buyer session, approve the one order and return using
   the configured callback. Expected API/DB: `CHECKOUT_APPROVED` only after a
   fresh provider order lookup validates the mapped payee, USD, and `0.01`.
7. With explicit confirmation, invoke capture once. Expected DB before provider
   response: exactly one `CAPTURE_CLAIMED` event, attempt `UNKNOWN`, reservation
   `OUTCOME_UNKNOWN`, and a distinct capture idempotency key. Expected final
   result after valid `COMPLETED`: attempt `SUCCEEDED`, reservation `CAPTURED`,
   capture ID, `CAPTURE_COMPLETED`, and reconciliation/audit evidence.
8. Do not retry a timeout, 5xx, unreadable response, pending result, mismatched
   provider payload, or failed callback. Expected safe outcome: unknown/hold
   plus event evidence; use the owner-scoped reconciliation operation only after
   a separate review decision.
9. Export only redacted evidence: timestamps, internal correlation IDs, state
   transitions, and masked/truncated provider IDs. Destroy/revoke temporary
   Sandbox material as appropriate.

## Redaction, rollback, and recovery

Never record client secret, OAuth access token, session cookie, raw `Authorization`
header, complete PayPal request/response bodies, buyer email/name, or full
merchant/account identifiers in source, logs, screenshots, the Devpost page, or
video. Redact provider IDs except an approved short suffix and use generated
synthetic identities.

There is no safe “rollback” of an uncertain capture. Preserve the attempt and
reservation in their unknown state, retrieve the existing provider order, and
record reconciliation evidence. Do not delete audit records, regenerate an
idempotency key, create a replacement order, or re-run capture to discover what
happened. For a definitively failed/not-submitted operation, follow the normal
state transition only after its recorded evidence has been reviewed.

## Approval gates and blockers

| Gate | Separate owner approval required? | Why |
| --- | --- | --- |
| Run migrations / create test DB | Yes | Writes durable database state. |
| Start/restart API, frontend, Docker, or Ollama | Yes | Changes service state. |
| Execute Sandbox OAuth or any provider GET | Yes | Contacts PayPal and uses credentials. |
| Create reservation/order or buyer checkout | Yes | Creates financial workflow state. |
| Capture or reconciliation action | Yes | Can affect payment state and DB evidence. |
| Deploy or expose any service | Yes | Creates public/security exposure. |

Current blockers: live Sandbox validation remains UNKNOWN; a full transitive
dependency lock is absent; the legacy recovery helper is quarantined rather
than demo-ready; and the repository still needs owner-approved licensing and
judge-access decisions.

**Exact next authorized action:** review this report and authorize either (A) a
read-only `paypal_sandbox_local.py check` that contacts Sandbox OAuth, or (B) the
controlled USD 0.01 end-to-end plan above. Option A is the smallest external
step and must be performed before any financial workflow action.
