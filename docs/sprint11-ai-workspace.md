# Sprint 11 — AI Proposal Workspace

Implemented frontend-only changes on `feature/intent-contract-lifecycle`, preserving
the uncommitted Sprint 4–10 adapter, timeout, diagnostics, and tests. No live
proposal POST, model generation, backend change, database operation, payment,
service restart, staging, commit, or push was performed.

## UI and behavior

`/agents` is now the AI Purchasing Assistant, using existing surface, border,
accent, typography, focus, theme, navigation, and responsive layout conventions.
The request editor has labels, a character counter, a 4,000-character maximum,
whitespace validation, synthetic example buttons, and optional approved-contract
selection. Lack of contracts does not prevent planning. Authenticated proposal
history establishes account readiness; an expired session disables creation and
offers account access. No session token or request payload is put in browser
storage or console logs.

Each explicit submission gets one fresh UUID Idempotency-Key and one fetch.
A synchronous ref prevents duplicate submits before React updates disabled
buttons. Waiting shows elapsed time and has a finite 340-second browser deadline,
longer than the existing 330-second proxy setting. Stop waiting aborts browser
fetch only: it makes no claim about server cancellation. Timeouts, network errors,
server failures, conflicts, and unverified success responses retain the submission
reference and block another creation until history is refreshed and the user
explicitly acknowledges starting a new request. There are no automatic POST
retries. A session-change event clears saved data and aborts browser waiting.
The pending server operation can still complete and must be checked in history.

Reusable proposal cards display the actual `proposal_id`, provider, persisted
status, created time, extracted purpose, merchant, amount/currency, contract,
policy result and explanation, and missing-information fields. DRAFT is shown as
not evaluated when its policy decision is null. Original request text is
collapsible. Payment preparation appears only when present in the API response.
No raw thinking or invented financial/AI fields are displayed.

`/agents/[proposalId]` is a new authenticated, read-only saved-proposal view with
manual refresh, loading, unavailable/authentication, and connection-error states.
It validates UUID route syntax and uses only the existing detail GET endpoint.
The workspace layout adds a Suspense boundary because Next.js 16 Cache Components
requires runtime pathname/params access to be suspended on this dynamic route.
The production build demonstrated and validated this requirement.

Existing review actions remain separate from generation. Confirmation, rejection,
payment preparation, and checkout retain distinct explicit confirmations.
Re-evaluation has its own button. Creating a proposal does not invoke any of them.
The saved detail page has no mutation buttons. Preparing payment explicitly warns
that it reserves budget and creates a local payment attempt; checkout has its own
confirmation and prior-failure warning. Backend policy checks are unchanged.

## API contracts

- GET `/api/agents/proposals`: authenticated `{items: ProposalResponse[]}` history.
- GET `/api/agents/proposals/{proposal_id}`: authenticated saved detail.
- GET `/api/contracts?limit=100&offset=0`: optional approved-contract choices.
- POST `/api/agents/proposals`: `{request, contract_id: UUID | null}`, authenticated
  same-origin cookies, UUID `Idempotency-Key`, no automatic retry. A complete 201
  or idempotent 200 result is runtime-checked before displaying it as saved.
- Response ID is `proposal_id`, never `id` or `proposalId`. Actual persisted
  statuses are DRAFT, NEEDS_INFORMATION, READY_FOR_REVIEW, REJECTED, CONFIRMED.
- Existing explicit actions use `/evaluate`, `/confirm`, `/reject`, and
  `/prepare-payment` under the proposal detail endpoint. Existing checkout uses
  the payment client only after a separate confirmation. No new API was added.

Creation can persist a DRAFT even when the response later fails. Refreshing
history, rather than retrying creation, is the recovery path. Results and history
are account scoped by the backend; this frontend does not bypass authentication.

## Exact Sprint 11 files

Modified:

- `apps/web/src/app/(workspace)/layout.tsx`
- `apps/web/src/app/(workspace)/agents/page.tsx`
- `apps/web/src/components/agents/agent-workspace.tsx`
- `apps/web/src/lib/agents/client.ts`

Added:

- `apps/web/src/app/(workspace)/agents/[proposalId]/page.tsx`
- `apps/web/src/components/agents/proposal-card.tsx`
- `apps/web/src/components/agents/proposal-detail.tsx`
- `apps/web/playwright.agents.config.ts`
- `apps/web/tests/e2e/agent-workspace.spec.ts`
- `docs/sprint11-ai-workspace.md`

## Verification

From `apps/web`, with the existing frontend running on port 3000:

```sh
npx --no-install playwright test --config playwright.agents.config.ts
npx --no-install tsc --noEmit --incremental false
npx --no-install eslint .
node --test tests/proxy-offline.test.cjs
git diff --check
```

Results: 17 mocked browser tests passed (15 new workspace cases plus both existing
agent tests unchanged), TypeScript passed, full ESLint passed, two existing proxy
wrapper tests passed, and diff whitespace checks passed. Tests cover snake_case
ID mapping, optional null contract, HTTP 201 rendering, OLLAMA and NEEDS_INFORMATION,
UUID freshness, synchronous double-submit prevention, cancellation, timeout,
network/server/malformed-response outcomes with no retries, authentication
expiry, session-change cleanup, validation, read-only refresh/detail, DRAFT and
rejected history, empty history, responsive overflow and keyboard focus, and
absence of automatic confirmation/payment/contract mutations.

The additional test configuration uses a fresh headless Chrome profile against
the existing frontend, without starting any services. The new suite intercepts
every API request and blocks external hosts; the existing agent suite already
mocks every API path. Pending mock requests are aborted at teardown. No actual
API POST reaches the proxy. Browser clock simulation exercises the 340-second
waiting limit without sleeping that long.

Production compilation and prerendering passed with:

```sh
INTENTRA_NEXT_DIST_DIR=.next-build-sprint11-webpack npm run build -- --webpack
```

All 19 static pages generated and the new detail route was partially prerendered.
Default Turbopack build remained blocked by an environment-level internal worker
port-binding EPERM, including after escalation. Webpack is the supported build
fallback used for validation; the repository's default bundler was not changed.
Build-generated tsconfig include paths were removed, and ignored next-env imports
were restored to the running development output directory. No frontend/backend
service was restarted.

Synthetic screenshots (no real proposal or account data):

- `/tmp/intentra-sprint11-desktop.png` — 1440px viewport.
- `/tmp/intentra-sprint11-mobile.png` — 390px viewport.

## Manual browser verification

1. Open `http://127.0.0.1:3000/agents` in the existing authenticated browser.
   Confirm the title, optional contract choice, 4,000-character counter, and
   existing proposal history. Do not submit a live request without authorization.
2. Inspect the existing verified proposal
   `68685df6-c0b5-40ff-a1f4-6a70b939d760`. Confirm its actual ID, OLLAMA provider,
   NEEDS_INFORMATION result, missing fields, and absence of payment preparation.
3. Follow View saved proposal to
   `/agents/68685df6-c0b5-40ff-a1f4-6a70b939d760`. Use Refresh proposal, then
   return to the workspace and Refresh history. These are read-only operations.
4. Resize between mobile and desktop, tab through the labels and controls, and
   expand Original request and Review actions. Do not click mutation actions.
5. Use the mocked browser test command above to exercise Create proposal, Stop
   waiting, timeout, authentication failures, and safety boundaries without
   inference or database writes.

Remaining limits: default Turbopack production build needs its worker-binding
environment resolved; browser tests ran against development mode rather than a
separate production server. No new live creation test was performed or authorized.
