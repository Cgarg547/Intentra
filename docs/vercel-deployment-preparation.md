# Vercel deployment preparation

This prepares the **Next.js web application** for Vercel. The FastAPI service,
PostgreSQL database, local Ollama daemon, and PayPal Sandbox credentials are
separate services. Do not deploy or expose any of them merely by deploying the
web project.

## Required topology

Deploy `apps/web` as the Vercel project root and deploy the API to an HTTPS
runtime that can reach its managed PostgreSQL database. A Vercel deployment
cannot use `127.0.0.1:8000` or a developer's local Ollama process.

For each Vercel environment that is intentionally enabled, configure these
server-only variables in Vercel:

| Variable | Value |
| --- | --- |
| `INTENTRA_API_PROXY_TARGET` | API HTTPS origin, e.g. `https://api.example.com` |
| `INTENTRA_API_URL` | Same API HTTPS origin; used only by server-side checkout callbacks |

The web build deliberately fails on Vercel if `INTENTRA_API_PROXY_TARGET` is
missing. This prevents `/api/*` requests from silently targeting a loopback
address. `INTENTRA_API_URL` is checked at callback time; an absent or malformed
value fails closed without contacting an API. Never use a `NEXT_PUBLIC_` prefix
for either value.

On the API deployment, configure exact values for the intended web origin:

| Variable | Value |
| --- | --- |
| `INTENTRA_FRONTEND_URL` | Exact HTTPS web origin |
| `INTENTRA_ALLOWED_ORIGINS` | Same exact origin; enforced for state-changing routes |
| `INTENTRA_CORS_ORIGINS` | Same exact origin; browser CORS response allowlist |
| `DATABASE_URL` | Managed, non-development PostgreSQL connection URL |

PayPal Sandbox values remain API-only secrets. `AGENT_AI_PROVIDER=ollama` is not
valid on a typical Vercel/API split unless the API runtime has an intentionally
private reachable Ollama deployment. Keep the default mock provider until that
separate topology and its security review are complete.

## Before approving a deployment

1. Set Vercel Root Directory to `apps/web`; leave the standard Next.js build
   command unless the platform requires otherwise.
2. Use a fresh, non-development database for the API. Apply migrations only
   after reviewing the target and backup/rollback plan.
3. Configure only a stable HTTPS web domain initially. Preview URLs are not
   automatically trusted by the API origin checks.
4. Build with the required variables, then verify `/health`, authenticated web
   requests through `/api`, and a mock-only checkout configuration. Do not use
   a PayPal order, buyer approval, or capture as a deployment smoke test.
5. Add production cookie/HTTPS, monitoring, rate limiting, backups and incident
   response review before representing the prototype as production-ready.

No deployment, database migration, provider call, or public URL is created by
this preparation document.
