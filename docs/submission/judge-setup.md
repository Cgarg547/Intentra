# Judge setup (local prototype)

This is a local prototype, not a hosted judge environment. A fresh local clone
of the committed branch was rehearsed on 2026-11-06 for the frontend only:
`npm ci`, TypeScript, ESLint, offline proxy tests (2/2), and the isolated webpack
build passed. The backend dependency install, browser run, database workflow and
provider flow were not part of that rehearsal.

For installation, use the root [README](../../README.md). A new local checkout
needs Git, Node 22.22.3, Python 3.14.7, and access to the applicable npm and
Python package registries or approved mirrors. Install the documented frontend
and API dependencies before running checks. Docker Compose and PostgreSQL 17 are
not required for the offline checks; they are only for the separately approved,
stateful database path. PayPal Sandbox credentials, buyer/business accounts, and
a disposable database are not included and must never be requested from judges.

After the documented dependency installation, the safe offline checks are:

```sh
cd apps/api && .venv/bin/python scripts/offline_checks.py
cd ../web && npx --no-install tsc --noEmit --incremental false
npx --no-install eslint .
node --test tests/proxy-offline.test.cjs
INTENTRA_NEXT_DIST_DIR=.next-build-check npm run build -- --webpack
```

These commands use mocked providers or static compilation and do not establish a
database, start a service, run Ollama, or contact PayPal. The mocked Playwright
suite is separate: it requires an already-running local frontend and Chrome, but
does not start services and intercepts every API request. A provider
demonstration requires the owner to authorize each operation in the dedicated
[Sandbox demo runbook](../paypal-sandbox-demo-runbook.md).
