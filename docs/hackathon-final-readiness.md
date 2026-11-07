# INTENTRA final readiness — 2026-11-07

## Executive decision

**NO-GO for final submission today; PARTIAL for a controlled, owner-approved Sandbox rehearsal.**

The application has a complete local implementation of the governed purchase
flow: authenticated request, structured AI extraction, deterministic policy,
human confirmation, reservation, Sandbox checkout handoff, server-side provider
verification, one-time capture claim, reconciliation, and append-only audit
records. It must not be represented as a currently verified hosted end-to-end
demo: the deployable AI runtime and current PayPal Sandbox journey have not
been revalidated in this execution.

## Evidence status

| Area | Status | Evidence and limitation |
| --- | --- | --- |
| Frontend workspace | PASS | Dashboard, contracts, AI proposals/detail, approvals, payments, merchant, analytics, audit, security, settings, and status routes compile (19 routes). UI contains loading/error/empty states and mocked responsive checks. |
| Authentication and owner scope | PASS (offline test scope) | The present virtual environment ran the network-blocked backend offline suite successfully. Database-writing integration tests remain intentionally gated on a dedicated test database. |
| AI workflow | PARTIAL | Ollama extraction and deterministic policy/human-review boundaries are implemented. A Vercel deployment cannot reach local Ollama; no zero-cost hosted provider is configured or claimed. |
| PayPal Sandbox workflow | PARTIAL | Server OAuth/order/return verification/capture/reconciliation code and mocked tests exist. No live order, buyer approval, capture, or reconciliation was initiated in this pass. |
| Payment safety | PASS (source/offline-test scope) | Explicit confirmation, provider IDs, idempotency, durable capture claims, unknown-outcome holds, owner scope, and audit records are implemented. A live Sandbox rehearsal remains required. |
| Database/schema | PARTIAL | Repository head is `9d7f1a4c6b20`; no migration was applied. Runtime database compatibility was not rechecked in this pass. |
| Deployment readiness | PARTIAL | Webpack production build passes. Hosted API URL, HTTPS cookie/origin settings, provider secrets, and judge access need operator configuration/rehearsal. |
| Submission package | PARTIAL | README, Apache-2.0 `LICENSE`/`NOTICE`, architecture, setup, Devpost draft, demo script, video plan, screenshot checklist, and release checklist exist. Public repo/license recognition, video, form, and receipt are external pending actions. |

## Fresh checks in this pass

| Command | Result |
| --- | --- |
| `.venv/bin/python scripts/offline_checks.py` | PASS — 230 tests; runner blocks network/DNS and uses a dummy process-local database URL |
| `npx --no-install playwright test --config playwright.config.ts --workers=1` | PASS — 40 mocked Chromium cases, including desktop/tablet/mobile layouts, proposal idempotency, approvals, checkout return, capture/reconciliation state, and 401 classification |
| `npx --no-install tsc --noEmit --incremental false` | PASS |
| `npx --no-install eslint .` | PASS |
| `node --test tests/proxy-offline.test.cjs` | PASS — 3 tests |
| `INTENTRA_NEXT_DIST_DIR=.next-final-readiness npm run build -- --webpack` | PASS — 19 routes |
| `git diff --check` | PASS |

### Local AI activation evidence

The existing local Ollama daemon and `qwen3:4b` model were discovered by a
read-only model listing. A bounded invocation through INTENTRA's real Ollama
adapter completed in 11.2 seconds and returned the validated structured result
`{"purpose":"Buy a replacement keyboard","merchant_id":"office_store","amount":"20.00","currency":"USD"}`.
The invocation used only the local loopback daemon, a non-sensitive sample
request, and did not create a proposal, write a database record, or interact
with PayPal. This verifies genuine local inference, but does not change the
hosted-AI limitation.
| Full API suite | PARTIAL — correctly refuses collection without both `DATABASE_URL` and `INTENTRA_TEST_DATABASE`; no dedicated writable test database was supplied or created |
| Live Ollama / PayPal / Neon | NOT RUN — no credentials, provider operation, or database mutation authorization |

## Latest rerun evidence — 2026-11-07

All local checks below were rerun on branch `deploy/intentra-vercel-preview`.
The Playwright artifact was written as JSON to
`/private/tmp/intentra-playwright-results.json` (outside the repository, so no
generated test artifact is accidentally released).

| Command | Result |
| --- | --- |
| `.venv/bin/python scripts/offline_checks.py` | PASS — 230 passed in 1.81s |
| `npx --no-install playwright test --config playwright.config.ts --workers=1 --reporter=line` | PASS — 40 serial mocked Chromium cases; Playwright `test-results/.last-run.json` reports `status: passed` and no failed tests |
| `npx --no-install tsc --noEmit --incremental false` | PASS |
| `npx --no-install eslint .` | PASS |
| `node --test tests/proxy-offline.test.cjs` | PASS — 3 passed, 0 failed |
| `INTENTRA_NEXT_DIST_DIR=.next-final-validation npm run build -- --webpack` | PASS — 19 routes |
| `git diff --check` | PASS |

The earlier JSON report contained a genuine assertion failure (39 expected, one
unexpected), contrary to an earlier incorrect 40/40 summary. The UI rendered
`Your session has expired`; a case-sensitive test looked for `Session expired`.
The test assertion was corrected to the actual rendered phrase, and the full
serial rerun passed. The initial attempt was also blocked by the execution
sandbox from binding `127.0.0.1:8173`; approved local-only runs succeeded.

## Official requirements rechecked — 2026-11-07

The official rules list the deadline as November 12, 2026 at 12:00 PM Pacific.
They require a meaningful PayPal Sandbox integration and AI functionality, a
functional runnable demo, a public repository with a visible open-source
license, and a public YouTube demonstration shorter than three minutes. The
project must function as depicted. See the official rules and challenge pages:
<https://paypalaihackathon.devpost.com/rules> and
<https://paypalaihackathon.devpost.com/>.

## Known limitations and issues

| Priority | Status | Item |
| --- | --- | --- |
| P0 | OPEN | Rehearse one explicitly approved, disposable Sandbox workflow and retain redacted policy/order/capture/audit evidence. |
| P0 | OPEN | Establish a judge-accessible functional demo: public repository plus reproducible setup, or an approved hosted URL. |
| P0 | OPEN | Record and publish a public YouTube demo under three minutes, then complete Devpost and retain submission receipt. |
| P1 | OPEN | Hosted AI is unavailable without a separately selected provider; local Ollama remains the reproducible path only. |
| P1 | OPEN | Run database-writing integration tests only against an explicitly prepared, isolated test database. Offline and mocked-browser validation are complete. |
| P1 | OPEN | Configure production/preview HTTPS cookie, CORS/origin, API target, Neon isolation, and secret handling; smoke-test without payment mutation. |
| P2 | KNOWN | Product discovery/retail quote provenance is not implemented. INTENTRA extracts user-supplied purchase facts and must be described that way. |

## AI and PayPal declarations

- **AI:** local Ollama with `qwen3:4b` is the supported demonstration provider.
  It is not reachable from Vercel. No paid model provider has been enabled and
  no hardcoded response is presented as AI output.
- **PayPal:** Sandbox-only server integration is implemented. Orders/captures
  require explicit human actions; no production credential or live-money flow is
  configured. Unknown provider outcomes remain held for reconciliation rather
  than being retried blindly.

## Hosted-demo and Preview inspection — 2026-11-07

Read-only Vercel inspection found authenticated access to separate
`intentra-web` and `intentra-api` projects. The inspected web Preview returned
Vercel Authentication (HTTP 302 to Vercel SSO), so it is not judge-accessible.
The inspected API Preview returned Vercel `NOT_FOUND` for `/health`; its build
metadata lists only a zero-millisecond root build and it is not serving FastAPI.
This is an API project-root/deployment configuration failure, not an application
health result.

The web Preview has the required server-only API proxy variable names and the
API Preview has database/origin and AI-mode variable names configured. Values
were not read. The next safe deployment must fix the API project root to
`apps/api`, validate an API Preview `/health` 200, set the web Preview proxy to
that exact HTTPS origin, configure matching explicit origins, and disable
Deployment Protection for the authorized judge demo (or provide a judge access
method). No deployment or environment variable was changed.

No secure zero-cost hosted AI provider is configured. The installed `qwen3:4b`
runs only through local loopback Ollama; Vercel cannot reach it. Do not expose
that daemon publicly. A hosted solution requires a separately provisioned
free-tier provider/account, API-only secret configuration, and security review.
The reproducible demo path remains local Ollama as documented in
`apps/api/AI_PROVIDER.md` and `README.md`.

Groq is the documented preferred hosted path: the existing OpenAI-compatible
adapter accepts its HTTPS API base URL and validates every structured result
independently. No Groq credential is configured and no hosted inference has
been claimed. The single approved Sandbox order cannot be created because the
required local Sandbox credential and server-owned merchant-mapping file is
absent; no provider request has been made.

### Approved Preview attempt

The approved API Preview repair was deployed from the repository root using an
explicit `.vercelignore`; this reduced its package from generated local output
to 237 source files. The resulting API deployment is Ready at
`https://intentra-4p18mjxay-cgarg3s-projects.vercel.app`, but its `/health`
request returned `FUNCTION_INVOCATION_FAILED`. Vercel logs identify the exact
safe failure: direct CLI Preview did not receive `DATABASE_URL`, so FastAPI
refused to import. The existing branch-scoped Preview secret was not modified.
The local Sandbox config file required for the approved USD 0.01 rehearsal is
absent, so no PayPal request, order, or durable payment record was created.

### Verified Git-triggered Preview

After release commit `4f2ace2b7036ba1f48f92ae87b803597cf6e3c66` was pushed,
Vercel's branch deployment produced a healthy API Preview at
`https://intentra-7icfj1dgw-cgarg3s-projects.vercel.app` and a web Preview at
`https://intentra-gw2ded7sp-cgarg3s-projects.vercel.app`. The stable branch web
alias is `https://intentra-web-git-deploy-intentra-vercel-cc5dcf-cgarg3s-projects.vercel.app`.
The API `/health` returned HTTP 200 with `database_configured: true` and origin
protection enabled. The web project’s Preview Vercel Authentication was disabled
for judge access; application authentication remains enforced: unauthenticated
`/api/auth/me` returned HTTP 401 with `AUTHENTICATION_REQUIRED`.

A synthetic, non-delivery Preview user was registered (201), retrieved through
the web proxy (200), and logged out (204). No financial workflow record was
created. The first `.test` address attempt returned 422 before persistence;
temporary cookies and response files were removed after each smoke test.

### Final publication verification

On 2026-11-07, GitHub's public repository API confirmed that
`deploy/intentra-vercel-preview` is the default branch and detected the
repository's `Apache-2.0` license. The verified branch head is
`7f81f5ecc662543a3554f71c6b1ad582f7d52e0e`.

The public Preview URLs above are accessible without Vercel deployment
authentication. This does not change the local-only AI limitation or the
Sandbox limitation: no safeguarded local Sandbox configuration exists, so no
order, approval, capture, or reconciliation was attempted. No public video or
Devpost submission URL exists in the available authenticated tooling.

## Official submission requirements checked

The official rules require meaningful use of PayPal Sandbox and an AI tool, a
functional demo, public source with a visible open-source license, and a public
YouTube demonstration video under three minutes. They also require the project
to work as depicted. The deadline shown by the organizer is November 12, 2026,
12:00 PM Pacific. See the [official rules](https://paypalaihackathon.devpost.com/rules)
and [submission overview](https://paypalaihackathon.devpost.com/).

## Exact remaining human actions

1. Approve a single disposable Sandbox rehearsal (including the specific order
   and, separately, its capture) and provide the backend-only Sandbox config.
2. Install/verify `qwen3:4b` locally, or explicitly approve a zero-cost hosted
   provider after its terms, reliability, and secret handling are reviewed.
3. Create the documented Python environment, run the offline suite, and prepare
   an isolated test database before any database-writing integration tests. The
   environment and offline suite now pass; only the dedicated database remains.
4. Authorize the target-only deployment, configure its secret variables, then
   run read-only smoke checks. Do not deploy from this report alone.
5. Push/publish the reviewed public repository, verify GitHub detects
   Apache-2.0, record/upload the video, and complete the Devpost form/receipt.

## Repository and video inspection — 2026-11-07

`https://github.com/Cgarg547/Intentra` is publicly reachable and the release
branch is synchronized with `origin/deploy/intentra-vercel-preview` before the
current uncommitted release-candidate changes. GitHub's public repository API
reports the default branch as `feature/intent-contract-lifecycle` and reports
no detected license. The repository contains an Apache-2.0 `LICENSE`, but the
default branch must contain that file (or the default branch must be changed to
the reviewed release branch) before license detection can be verified. No
commit, push, default-branch change, or visibility change was made.

The local macOS screen-capture utility is available, but no video encoder or
authenticated YouTube uploader was found. The authentic recording script,
metadata guidance, and redaction requirements are prepared under
`docs/submission/`. Do not record mocked screens as verified Sandbox activity
or publish any video without final publication approval.

## Authorized-later deployment commands

From `apps/web`, after setting the authorized HTTPS API target:

```sh
INTENTRA_API_PROXY_TARGET=https://YOUR-API-HOST npm run build -- --webpack
vercel --prod
```

From `apps/api`, only after reviewing the Neon target and approving migrations:

```sh
.venv/bin/alembic current
.venv/bin/alembic upgrade head
```

Do not run a migration, `vercel`, Sandbox order creation, or capture without
the corresponding separate approval.
