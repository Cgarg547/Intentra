# INTENTRA web workspace

This is the Next.js App Router frontend for INTENTRA's human-governed purchasing
workflow. It provides authenticated contracts, AI purchase proposals, approval
review, payment history, audit records, and safe PayPal Sandbox checkout return
handling. The UI never treats a browser redirect as proof of payment success.

## Local development

Install dependencies once:

```sh
npm ci
```

Start the frontend only on an unused local port. The default development API
proxy is `http://127.0.0.1:8000`; use the same browser hostname as the API
session and checkout callback configuration.

```sh
npm run dev -- --hostname 127.0.0.1 --port 3000
```

For the complete safe local API setup, mock-mode configuration, and provider
boundaries, read the repository [README](../../README.md).

## Verification

These checks do not contact Ollama or PayPal:

```sh
npx --no-install tsc --noEmit --incremental false
npx --no-install eslint .
node --test tests/proxy-offline.test.cjs
INTENTRA_NEXT_DIST_DIR=.next-build-check npm run build -- --webpack
```

The mocked Playwright suite requires a separately running local frontend. Every
API request is intercepted before it can reach the development proxy:

```sh
PLAYWRIGHT_BASE_URL=http://127.0.0.1:3000 \
  npx --no-install playwright test --config playwright.agents.config.ts
```

## Vercel

Deploy this directory (`apps/web`) as the Vercel project root. Vercel hosts only
the frontend; the FastAPI service, PostgreSQL, and any Ollama inference runtime
must be separately deployed and privately configured. Set server-only
`INTENTRA_API_PROXY_TARGET` and `INTENTRA_API_URL` to the HTTPS API origin.
Do not prefix either variable with `NEXT_PUBLIC_`.

See [the deployment preparation guide](../../docs/vercel-deployment-preparation.md)
before configuring hosting, origins, secrets, migrations, or a deployment.
