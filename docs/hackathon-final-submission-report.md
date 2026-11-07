# INTENTRA hackathon final submission report

**Status: NO-GO for final submission; local release candidate validated.**

Date: 2026-11-07<br>
Branch: `deploy/intentra-vercel-preview`<br>
Repository target: `https://github.com/Cgarg547/Intentra`

## Verified local evidence

| Check | Result |
| --- | --- |
| Backend network-blocked offline suite | PASS — 230 passed in 1.81s |
| Serial mocked Playwright Chromium suite | PASS — 40 cases; `test-results/.last-run.json` reports `status: passed` and no failed tests |
| TypeScript | PASS |
| ESLint | PASS |
| Proxy offline tests | PASS — 3 passed |
| Next.js production build | PASS — 19 routes |
| Patch whitespace validation | PASS — `git diff --check` |

The prior JSON result contained one case-sensitive assertion failure (39/40).
It was corrected and a complete serial rerun passed; Playwright's current
machine-readable `test-results/.last-run.json` records the clean status. The
older failing JSON is retained outside the repository for audit only.

## Implemented and tested scope

INTENTRA implements the governed purchase path: authenticated workspace access,
contract and merchant context, AI-backed structured proposal extraction,
missing-information states, deterministic policy evaluation, explicit human
approval/rejection, payment reservations, PayPal checkout handoff, provider
outcome verification, one-time capture claims, reconciliation, and audit
evidence. Browser coverage includes desktop, tablet, and mobile navigation,
responsive containment, accessible drawer controls, proposal idempotency,
session/error behavior, approval/check-out return states, and payment safety
paths.

The supported AI demo runtime is local Ollama using `qwen3:4b`. It is genuine
inference, not a mocked provider: on 2026-11-07 a bounded sample invocation
through INTENTRA's adapter returned the validated expected purchase structure in
11.2 seconds. It used the local loopback daemon only and created no proposal or
database record. It is not accessible from Vercel. No paid hosted model was
enabled.

## External validation status

| Artifact or action | Status |
| --- | --- |
| Live Ollama inference | PASS — local `qwen3:4b` adapter invocation returned validated structured output in 11.2s, without persistence |
| PayPal Sandbox order, buyer approval, capture, reconciliation | Blocked before provider contact — the required local 0600 Sandbox config/merchant mapping is absent; no order was created |
| Dedicated writable test database / remote migrations | Not executed; no disposable database authorization supplied |
| Preview deployment and public smoke test | PASS — Git-triggered Preview API health is 200; public web alias is reachable; synthetic register/me/logout sequence passed and protected API is 401 without a session |
| Git commit/push/public repository verification | PASS — public repository default branch is `deploy/intentra-vercel-preview`; GitHub detects Apache-2.0. Verified branch head: `7f81f5ecc662543a3554f71c6b1ad582f7d52e0e`. |
| Video capture, YouTube public upload | Not executed; no recording/upload account tooling or final publication approval |
| Devpost draft/final submission | Not executed; no authenticated Devpost session or final submission approval |

## Hosted and deployment findings

No secure zero-cost hosted AI configuration exists in the current environment.
The verified `qwen3:4b` runtime is local loopback Ollama and cannot be reached
from Vercel. Exposing it publicly would be unsafe. The reproducible local demo
is documented; a hosted solution needs a separately provisioned free-tier
provider, API-only secret/configuration, and security review.

The earlier web Preview was protected by Vercel Authentication and was not
judge-accessible. A corrected direct API package deployment reached Vercel Ready at
`https://intentra-4p18mjxay-cgarg3s-projects.vercel.app`, but `/health`
returned `FUNCTION_INVOCATION_FAILED`: its logs show FastAPI correctly failed
closed because direct CLI Preview did not receive `DATABASE_URL`. The original
branch-scoped Preview secret was not changed; the required local Sandbox config
file is also absent. No web redeploy, remote migration, PayPal request, order,
or capture was performed.

The Git-triggered API Preview is healthy at
`https://intentra-7icfj1dgw-cgarg3s-projects.vercel.app`; its `/health` returns
HTTP 200 with `database_configured: true` and origin protection enabled. The
public judge web alias is
`https://intentra-web-git-deploy-intentra-vercel-cc5dcf-cgarg3s-projects.vercel.app`.
Its unauthenticated `/api/auth/me` response is HTTP 401 with
`AUTHENTICATION_REQUIRED`. A synthetic Preview account register (201), session
lookup (200), and logout (204) smoke test passed without any payment records.

## Public repository finding

`https://github.com/Cgarg547/Intentra` is public and reachable. On 2026-11-07,
the authorized default branch was changed to `deploy/intentra-vercel-preview`.
GitHub's public repository API subsequently detected the Apache-2.0 license.
The verified release head is `7f81f5ecc662543a3554f71c6b1ad582f7d52e0e`.

## Final external limitations

No dedicated local Sandbox configuration file is present, so the mandatory
merchant mapping and disposable-local-database preflight cannot pass. No PayPal
order was created and no capture was attempted. The only genuine AI evidence is
the documented local loopback Ollama inference; there is no hosted AI provider.
No authenticated YouTube publisher or Devpost submission session/tool is
available, so neither a public video nor a Devpost receipt/URL is claimed.

## Official-rule alignment

As checked on 2026-11-07, the official PayPal AI Hackathon rules require
meaningful use of PayPal Sandbox and AI, a functional demo, public open-source
source with a visible license, and a public YouTube video under three minutes.
The deadline is November 12, 2026 at 12:00 PM Pacific. Reference:
<https://paypalaihackathon.devpost.com/rules>.

## Final decision

**NO-GO** until a controlled Sandbox rehearsal is explicitly approved and
completed, a judge-runnable demo/public repository is verified, a public video
is published, and the Devpost form is submitted with its receipt. No URLs,
captures, deployment, or submission are claimed without verification.
