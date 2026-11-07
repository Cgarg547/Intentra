# INTENTRA Preview deployment recovery report

Date: 2026-11-06<br>
Branch inspected: `deploy/intentra-vercel-preview` at `3e1dce0`
## Readiness verdict

**NO-GO for claiming a functional Preview deployment.** The source now builds and
its offline security checks pass, but the deployed API was previously observed
returning `DEPLOYMENT_NOT_FOUND`/404 and its Vercel project configuration,
Preview environment bindings, and Neon schema have not been verified from this
checkout. The required external actions below must be completed before a GO.

## Root causes and recovery

| Observed issue | Root cause | Safe recovery |
| --- | --- | --- |
| Web loads while System Status/authenticated views are unavailable | The recorded API origin returned Vercel 404 rather than FastAPI, so a successful web build did not prove the API target was live. | Set the API project root to `apps/api`, confirm it deploys this branch, then verify `GET /health` returns 200. |
| Registration says `Untrusted request origin` | State-changing requests are correctly rejected unless the browser's exact web origin is in `INTENTRA_ALLOWED_ORIGINS`. Preview aliases are not implicitly trusted. | Configure the exact stable Preview web HTTPS origin (no trailing slash) in the API Preview environment; do not add a wildcard. |
| Contracts, agents, payments, approvals, analytics, security, audit report expired sessions | API 401s were flattened in some web clients. An API/proxy/deployment-protection 401 could look like a session expiration. | Web clients now distinguish `AUTHENTICATION_REQUIRED`, `SESSION_INVALID`, and un-coded upstream/protection failures. |
| Web may target the wrong backend | The Next rewrite target is build-time server configuration. A successful build only proves a target is syntactically present. | Set both server-only web Preview variables to the matching API Preview origin and rebuild the web deployment. |
| Old aliases return `DEPLOYMENT_NOT_FOUND` | This is Vercel deployment/alias state, not an application route response. | Inspect project deployments and aliases in Vercel; do not alter aliases automatically. |
| Ollama may appear usable from deployment | A Vercel function cannot reach a developer's loopback Ollama daemon. | Use `AGENT_AI_PROVIDER=mock` and `AGENT_LLM_ENABLED=false` for Preview unless a separately reviewed private provider is reachable. No generation was attempted. |

## Source changes

- `apps/api/main.py` — adds non-sensitive `/health` configuration-state diagnostics (`database_configured`, origin protection enabled).
- `apps/api/tests/test_origin_protection_offline.py` — offline tests for explicit trusted origins, untrusted-origin rejection, and safe health output.
- `apps/web/src/lib/auth/client.ts` — preserves safe API error codes.
- `apps/web/src/lib/workspace/client.ts` — separates sign-in, expired-session, and unavailable/protected API states.
- `apps/web/src/lib/contracts/client.ts` — applies the same classification to contract reads and mutations.
- `apps/web/src/lib/agents/client.ts` — applies the same classification to proposal history/actions.
- `apps/web/src/app/account/page.tsx` — removes inaccurate local-development wording.

The existing Next.js rewrite remains `/api/:path*` to the server-only
`INTENTRA_API_PROXY_TARGET`; FastAPI origin protection, CSRF/origin checks,
HttpOnly cookies, `SameSite=Lax`, and deployed `Secure` cookie behavior remain
enabled. No wildcard credentialed CORS was added.

## Verification results

| Command | Result |
| --- | --- |
| `DATABASE_URL=postgresql+asyncpg://offline:offline@127.0.0.1:1/offline .venv/bin/python -m pytest -q tests/test_origin_protection_offline.py tests/test_auth_security.py tests/test_database_url_normalization.py` | PASS — 15 tests |
| `.venv/bin/python scripts/offline_checks.py` | PASS — 230 tests; runner blocks network access |
| `npx --no-install tsc --noEmit --incremental false` | PASS |
| `npx --no-install eslint .` | PASS |
| `node --test tests/proxy-offline.test.cjs` | PASS — 3 tests |
| `INTENTRA_API_PROXY_TARGET=https://api.preview.invalid INTENTRA_API_URL=https://api.preview.invalid VERCEL=1 INTENTRA_NEXT_DIST_DIR=.next-build-recovery npm run build -- --webpack` | PASS |
| `node --test tests/proxy-transport.test.cjs` | PARTIAL — sandbox blocks local loopback binds; one isolated rerun completed its first synthetic transport case. Re-run in a normal CI runner. |

No hosted database, PayPal endpoint/order/reservation/capture/refund, or AI
provider/generation endpoint was invoked. Test PayPal implementations are
offline fakes and the reviewed runner denies network sockets.

## Required Vercel configuration (names only)

Configure these as server-only values; never use `NEXT_PUBLIC_` prefixes.

| Project | Scope | Required variables |
| --- | --- | --- |
| `intentra-web` | Preview for `deploy/intentra-vercel-preview` | `INTENTRA_API_PROXY_TARGET`, `INTENTRA_API_URL` |
| `intentra-api` | Preview for `deploy/intentra-vercel-preview` | `DATABASE_URL`, `INTENTRA_FRONTEND_URL`, `INTENTRA_ALLOWED_ORIGINS`, `INTENTRA_CORS_ORIGINS`, `AGENT_AI_PROVIDER`, `AGENT_LLM_ENABLED` |
| `intentra-api` | Preview only if a separately approved Sandbox test is intended | `PAYPAL_SANDBOX_CLIENT_ID`, `PAYPAL_SANDBOX_CLIENT_SECRET`, `PAYPAL_SANDBOX_MERCHANTS` |

Use the matching API Preview HTTPS origin for both web variables. Use the exact
web Preview HTTPS origin, without a trailing slash, for all three API origin
variables. The safe Preview AI values are `mock` and `false`. Keep PayPal
variables absent for this recovery verification.

## Database and migrations

The repository Alembic head is `9d7f1a4c6b20`. Whether the selected Neon
Preview branch requires migrations is **unknown** because no connection was
made. Do not run migrations automatically.

Non-destructive operator plan:

1. Select a dedicated Neon Preview branch and take/confirm a backup.
2. Set only that branch's `DATABASE_URL` in the API Preview scope.
3. From `apps/api`, run `alembic current`, confirm the target identity and
   revision, then compare it with `alembic heads`.
4. Review generated migration SQL/rollback implications and obtain approval.
5. Only then run `alembic upgrade head`; record the resulting revision.

## Manual deployment checklist

1. Authenticate an operator with Vercel access and inspect deployment logs,
   alias history, project roots, branch settings, environment scopes, and
   deployment protection. This checkout could not validate those external
   settings.
2. Confirm `intentra-api` has root directory `apps/api` and serves FastAPI's
   `main:app`; confirm `intentra-web` has root directory `apps/web`.
3. Ensure deployment protection permits the web rewrite to reach the matching
   API Preview, or use an approved service-to-service bypass mechanism. Do not
   weaken browser authentication or CORS to solve this.
4. Apply the variable scopes above and redeploy API first, then web, from the
   target branch. Do not change production aliases.
5. Record a read-only `GET /health` 200 on the deployed API. Through the web
   Preview, register a synthetic account, confirm `/api/auth/me`, and inspect
   owner-scoped empty views. Do not create reservations or use checkout/AI
   generation as a smoke test.
