# INTENTRA final hackathon report — 2026-11-06

## Release result

INTENTRA is **PARTIAL** for public hackathon submission and **ready for a
controlled, owner-approved PayPal Sandbox rehearsal**. This pass used only
isolated disposable databases/services for local verification and created the
current local release-preparation commit; no provider call, push, deployment,
upload, or submission was
performed.

## Requirement matrix

| Priority | Requirement | Status | Evidence / limitation |
| --- | --- | --- |
| P0 | AI is separated from payment authorization | PASS | Source uses extraction followed by deterministic contract/merchant/currency/budget policy and explicit human confirmation. |
| P0 | PayPal Sandbox integration is implemented | PARTIAL | OAuth, Orders, return validation, capture and reconciliation source paths exist; no current linked Sandbox transaction was run. |
| P0 | Duplicate and unknown-outcome protections | PASS (offline baseline) | Durable create/capture keys, capture claims and UNKNOWN holds are in source; verified selected offline baseline is 218 tests. |
| P0 | Controlled USD 0.01 Sandbox rehearsal | UNKNOWN | Prepared in `docs/paypal-sandbox-demo-runbook.md`; requires separate approvals for DB/service/provider operations. |
| P0 | Public source and Apache-2.0 recognition | PARTIAL | Local `LICENSE` and `NOTICE` are tracked; publication and GitHub recognition have not occurred. |
| P0 | Accurate video, Devpost and receipt | UNKNOWN | Recording script, upload instructions and receipt placeholder exist; external artifacts are owner actions. |
| P0 | Judge setup/access | PARTIAL | Local/offline setup is documented; fresh-clone and hosted/public judge access are unverified. |
| P1 | Discoverable responsive B2B workflow | PASS (mocked baseline) | Workspace navigation and command center cover contracts, agents, approvals, payments and audit. Owner-reported mocked Playwright baseline is 35 cases. |
| P1 | Auth and owner-scoped access | PASS (offline baseline) | Session/ownership tests are selected by the offline runner; no new backend run was possible in this sandbox. |
| P1 | Developer experience and CI | PASS (local static checks) | VS Code tasks cover API offline, type/lint, proxy, isolated build and mocked browser checks; CI YAML covers offline API/web static checks. |
| P1 | Production security posture | PARTIAL | Local prototype retains loopback topology and non-production cookie/origin/security limitations documented in README. |
| P1 | Dependency reproducibility | PARTIAL | Node lockfile and pinned direct Python requirements exist; no hash-locked Python transitive set or fresh-clone proof. |
| P2 | Product catalog/discovery | FAIL (not implemented) | INTENTRA extracts explicit facts only; no discovery/search/quote provenance is claimed. |
| P2 | Optional sponsor integrations | NOT APPLICABLE | No additional sponsor/tool integration is claimed. |
| P2 | Distribution notice inventory | PARTIAL | License review exists; any distributed binaries, model artifacts, images or media need final provenance review. |

## Changes made in this pass

- Updated stale readiness evidence to the current verified baseline of 218
  backend offline and 35 mocked browser tests in
  `docs/hackathon-master-plan.md` and `docs/hackathon-readiness.md`.
- Added safe VS Code tasks for offline proxy tests and an isolated production
  webpack build in `.vscode/tasks.json`.
- Completed submission materials: Devpost title/tagline/problem/solution/sponsor
  disclosure, YouTube procedure and public-URL placeholder, release-evidence
  ledger, and a Devpost receipt placeholder under `docs/submission/`.
- Payment-safety paths continue to preserve explicit approval, durable claims,
  and UNKNOWN holds.
- Added the missing pinned `greenlet==3.5.6` runtime dependency required by
  SQLAlchemy's async engine. A clean Python 3.14 installation had otherwise
  failed before migrations.
- Restored proposal diagnostic correlation compatibility: valid incoming
  `X-Correlation-ID` values are now preserved as a legacy response header while
  the canonical `X-Intentra-Correlation-ID` remains present. This changes no
  payment authorization, idempotency, provider, or audit behavior.

## Reviewed release-preparation file set

- `.vscode/tasks.json`, `README.md`
- `apps/api/intentra/middleware/origin.py`, `apps/api/requirements.txt`,
  `apps/api/scripts/offline_checks.py`
- `docs/final-hackathon-checklist.md`,
  `docs/hackathon-execution-progress.md`, `docs/hackathon-final-report.md`,
  `docs/hackathon-master-plan.md`, `docs/hackathon-readiness.md`
- `docs/submission/architecture.md`, `demo-script.md`,
  `devpost-description.md`, `final-submission-checklist.md`,
  `judge-setup.md`, `release-readiness.md`, `screenshots-checklist.md`,
  `technologies.md`, and `youtube-upload.md`

The requested `evidencethat` typo was not present in the current checkout, so no
blind replacement was made.

## Checks observed in this pass

| Check | Result |
| --- | --- |
| `npx --no-install tsc --noEmit --incremental false` | PASS (2026-11-06) |
| `npx --no-install eslint .` | PASS (2026-11-06) |
| `node --test tests/proxy-offline.test.cjs` | PASS (2 tests) |
| `INTENTRA_NEXT_DIST_DIR=.next-build-check npm run build -- --webpack` | PASS (2026-11-06; 19 routes) |
| `git diff --check` | PASS |
| API offline runner | PASS (2026-11-06): 218 selected tests in 2.39s, with network/DNS blocked by the runner |
| Full API suite | NOT RE-RUN in this execution session. The previously reported isolated-PostgreSQL result is historical evidence, not a fresh claim. |
| Mocked Playwright | PASS (2026-11-06): 35/35 Chromium tests using only the repository's isolated mock API/frontend configuration |
| `node --test tests/proxy-transport.test.cjs` | NOT RUN TO COMPLETION: sandbox denied loopback binding (`listen EPERM 127.0.0.1`) before all five isolated transport cases. On the owner Mac, run this exact command from `apps/web`. |
| Fresh clone frontend rehearsal | PASS (2026-11-06): a separate clone of committed HEAD passed `npm ci`, TypeScript, ESLint, 2 offline proxy tests, and isolated webpack build. Backend dependency installation and browser tests were not included. |

The requested local Ollama inference and Sandbox OAuth connectivity check could
not run: `ollama list` did not contain `qwen3:4b`, and neither the private
Sandbox configuration file nor any required credential environment variable was
present. No credential value was read, printed, or substituted; no provider
request was made.

## Approval-gated next actions

1. Supply/install the dedicated private Sandbox configuration and local
   `qwen3:4b` model, then rerun the already-authorized read-only OAuth preflight.
2. Approve exactly one synthetic USD 0.01 workflow, then separately approve its
   one-time capture. On any unknown result, stop and use GET-only reconciliation
   only after another review decision.
3. Approve pushing the current local release-preparation commit to the intended
   repository, public-source/license verification, and any hosted judge-access
   decision.
4. Record/upload the accurate ≤180-second video, verify its public URL, complete
   Devpost/eligibility fields and retain the final receipt before the deadline.

## Local release-preparation commit

The current local `chore: prepare hackathon release evidence` commit contains
the reviewed README, API safety/requirements updates, VS Code tasks, readiness
evidence, final report/checklist, and submission materials. Its staged diff
passed whitespace and credential-pattern reviews before committing.

It is local only: no push, publication, upload, or submission has occurred.
Before pushing, verify that every displayed claim is supported by the final
video, provider evidence, and public source.
