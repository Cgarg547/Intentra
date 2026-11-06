# INTENTRA Vercel live verification

Verification date: 2026-11-06

## Target topology

| Component | Intended URL | Status |
| --- | --- | --- |
| Web | `https://intentra-web.vercel.app` | HTTP 200 verified |
| API | `https://intentra-api-iota.vercel.app` | HTTP 404 at `/health` and `/api/auth/me`; not serving FastAPI |
| Deployment branch | `deploy/intentra-vercel-preview` | Checked out at `61a2904` before the follow-up security fix |
| API function entrypoint | `apps/api/main.py` | Configured by `apps/api/vercel.json`; Vercel project root must be `apps/api` |
| Web project root | `apps/web` | Required |

The repository's `apps/api/vercel.json` explicitly builds `main.py` with
`@vercel/python` and routes every path to that function. If Python source is
published as static content, the API Vercel project's root directory is not
`apps/api` (or its deployment is using a stale commit/configuration).

## Source changes in this verification

The pending commit hardens auth cookies: a session cookie is marked `Secure`
when running on Vercel or when `INTENTRA_FRONTEND_URL` is HTTPS. Local HTTP
development remains supported. No secrets, environment files, payment behavior,
or database records were changed.

## Test evidence

| Check | Result |
| --- | --- |
| Focused backend unit tests | Pass: 103 tests |
| Backend offline checks | Pass: 230 tests |
| Frontend ESLint | Pass |
| Next.js production build | Pass with `next build --webpack` |
| Proxy transport/offline tests | Pass: 4 tests |
| Mocked Playwright suite | Test bodies pass when run serially; the concurrent run hit a local Playwright trace-artifact `ENOENT` race during context teardown |
| Default Turbopack build | Blocked in this runner by `Operation not permitted` while Turbopack attempts a child-process port bind; webpack build is clean |

No PayPal order, approval, capture, or live AI provider call was made. The
mocked browser tests exercise synthetic data only.

## Database and migration status

No Neon credential or linked Neon CLI session was available to this checkout.
No database connection, migration, or schema mutation was attempted. The
repository's sole Alembic head is `9d7f1a4c6b20`.

Before migrating, an operator must identify a dedicated Neon preview branch,
confirm its database name/host, and set only that branch's asyncpg URL as the
API Preview `DATABASE_URL`. From `apps/api`, run `alembic current`, review the
target identity, then run `alembic upgrade head`. Do not use a local Compose URL
or the development database.

## Remaining blockers and exact operator actions

1. Renew the expired Vercel CLI token (`vercel login`) or grant project access.
   The saved token was rejected, so project IDs, Git production-branch settings,
   deployment logs, environment names, and aliases could not be inspected.
2. In Vercel, set the API project root directory to `apps/api` and the web
   project root directory to `apps/web`. Confirm both projects deploy commit
   `deploy/intentra-vercel-preview`, not the repository default branch
   (`feature/intent-contract-lifecycle` in this checkout's cached remote HEAD).
3. On the API **Preview** environment, configure server-only values:
   `DATABASE_URL` (dedicated Neon preview branch),
   `INTENTRA_FRONTEND_URL`, `INTENTRA_ALLOWED_ORIGINS`, and
   `INTENTRA_CORS_ORIGINS` (the exact intended HTTPS web preview origin), and
   `AGENT_AI_PROVIDER=mock`. Keep PayPal variables absent unless a separately
   approved Sandbox test requires them.
4. On the web **Preview** environment, configure server-only
   `INTENTRA_API_PROXY_TARGET` and `INTENTRA_API_URL` to the matching API
   preview HTTPS origin. Never use `NEXT_PUBLIC_` prefixes for these values.
5. Redeploy both previews, inspect the API function log for a successful import,
   then record `GET /health` as HTTP 200. Perform authenticated browser smoke
   tests through the web URL using a synthetic account. Do not create or capture
   PayPal orders.

## Live endpoint status

The final read-only public smoke check returned the following:

| Request | Expected status |
| --- | --- |
| `GET https://intentra-web.vercel.app/` | **200** |
| `GET https://intentra-api-iota.vercel.app/health` | **404** (`NOT_FOUND`) |
| `GET https://intentra-api-iota.vercel.app/api/auth/me` | **404** (`NOT_FOUND`) |

The public API domain is still not routing to FastAPI. This is consistent with
the API project being configured with the wrong root directory or an older
deployment. The Vercel token is invalid, so this could not be corrected or
verified through the CLI. The frontend's runtime API proxy and all authenticated
web workflows must be considered unverified until a 200 API health response is
observed from the matching preview.
