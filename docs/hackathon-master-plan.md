# INTENTRA — hackathon master build plan

Date: 2026-11-05 UTC. Deadline requested: **2026-11-12 12:00 Pacific (20:00 UTC)**.
Readiness: **PARTIAL**. Core authorization and provider integration are implemented;
product discovery, submission packaging and a reproducible linked demonstration
are incomplete. No sponsor eligibility or official score is guaranteed.

Start with the [readiness audit](hackathon-readiness.md): requirement matrix,
repository evidence E1–E13, five judging assessments, state aggregates and tests.
This plan uses its verified baseline rather than assuming sponsor integrations
or new backend capabilities exist. The audited baseline was the Sprint 11 interface. Concurrent frontend edits
appeared during Phase 0 and were preserved; this pass did not start the major
redesign. Current-source validation is recorded below.

## Verified capability and dependency map

| Area | Current capability | Missing / dependency |
| --- | --- | --- |
| Web | Next 16.4.3/React 19.3, authenticated Agents, saved detail, policies, approvals, payments, merchants, analytics, audit, status | Premium design consistency; Overview AI/budget summary; full judge setup |
| AI | Local Ollama qwen3:4b, think=false, 1024 output tokens, strict schema/financial grounding, finite timeout; verified real extraction | No product search, catalog comparison, autonomous tool loop, or quote provenance |
| Authorization | Owner-scoped approved contracts, exact merchant/currency, Decimal amount, version and remaining budget checks | No demonstrated organization RBAC, team approvals or arbitrary retailer checkout; do not advertise these |
| Financial workflow | Separate human proposal confirmation, preparation, buyer checkout, capture and reconciliation | Current Ollama NEEDS_INFORMATION proposal is not a completed payment journey |
| PayPal | Direct Sandbox OAuth/Orders/lookup/capture, persisted idempotency, identity/evidence validation | Current provider account/permissions not freshly verified; old-revision operator recovery script needs review |
| Persistence | PostgreSQL 17, Alembic head 9d7f1a4c6b20, append-only event triggers | Clean installation and stateful suite not verified in this no-writes audit |
| Submission | Public GitHub origin, substantive in-period work; Apache-2.0 approved and installed locally | Public license recognition, published current sprint source, final description/video and judge access verification |

Known runtime: Node 22.22.3, Python 3.14.7, Ollama server previously observed as
0.35.1. Model performance is hardware dependent. Deployment is not a transparent
copy: API rewrite currently targets loopback port 8000 and Ollama is loopback-only.

## Source-backed sponsor decision matrix

Prices/offers were checked from public vendor/sponsor documentation during this
session. Offers are not redeemed entitlements. Exact limits, retention, available
plans and eligibility can change; confirm the account-specific terms before use.
No signup, installation, purchase, integration call, deployment or data transfer
was performed. Listed effort is an estimate for meaningful, tested integration.

| Tool | Real benefit / recommendation | Credentials and cost/license evidence | Privacy/security and effort | Sponsor/demo assessment |
| --- | --- | --- | --- | --- |
| PayPal direct REST | **KEEP**, central existing payment boundary | Server Sandbox app credentials and verified seller mapping. Free Sandbox per hackathon rules; REST terms apply. [REST docs](https://developer.paypal.com/api/rest/) | Existing guarded server client; never expose secrets or allow model execution. Review/rehearse 4–8h with separate approval | Core integration already real code; historical capture is not a new provider verification |
| PayPal AI Toolkit | **EVALUATE as development assistance**, not a replacement payment engine | Coding-agent context/MCP plugin, Apache-2.0 shown by [official repo](https://github.com/paypal/AI-Toolkit). Actual API tools still need PayPal authorization; coding-agent costs separate | Tool installation can broaden capabilities; install only with approval, disable financial tools. 1–2h evaluation | No claim of use yet; provides development evidence only if genuinely used |
| PayPal Agent Toolkit | **DEFER runtime adoption**: existing deterministic path is safer to preserve | TypeScript/Python/framework function tools, Apache-2.0 [repo/license](https://github.com/paypal/agent-toolkit). PayPal credentials remain needed | A model tool-call API is not authorization. Route any tool through current owner/contract/human checks. 1–2 days | Not mandatory; importing a toolkit for appearance adds no judge value |
| Channel3 | **P1 candidate** for genuine product discovery | Server API key/account required. [Sponsor page](https://paypalaihackathon.devpost.com/details/channel3) advertises 20,000 credits/searches with PAYPAL-HACKATHON-2026 and no card. Service terms; SDK licensing/normal metered overage not verified | Only approved public shopping queries; no user/financial/session payloads. Server validation, cache and credit cap. 8–16h after docs/key approval | Sponsor page requires actual API or MCP use; a mock/stub/reference does not qualify. Highest fit, but not enabled |
| AG Grid Community | **P1/P2 candidate** for real transaction filtering and keyboard tables | MIT, $0 Community per [vendor licensing](https://www.ag-grid.com/license-pricing/); no API credential needed. React 19 works with AG Grid >=32.3 per [compatibility](https://www.ag-grid.com/react-data-grid/compatibility/) | Client-only owner-authorized rows; no model/cloud export. Pin compatible Grid/React/TS versions, 4–8h | Meaningful grid usage may qualify under rules; competitive sponsor guidance emphasizes richer custom dashboards, not a stock table |
| AG Studio / Enterprise | **DEFER unless trial and demo benefit approved** | [Sponsor](https://paypalaihackathon.devpost.com/details/aggrid) offers 45-day trial. Studio subscription/customer-facing Enterprise requires vendor terms/quote, not Community MIT. [Quick start](https://www.ag-grid.com/studio/react/quick-start/) | New library/license compatibility not tested on this app. AI dashboard prompts could disclose records; start without remote AI. 1–2 days | Guardrailed finance dashboards/custom widgets are relevant; do not claim Community includes Studio or perpetual free use |
| APIMatic | **OPTIONAL dev aid**, not a new product feature | [Sponsor](https://paypalaihackathon.devpost.com/details/apimatic): PayPal context plugin needs no extra APIMatic sign-in; used-plugin participants can claim one Basic month; winners six Business months. [Pricing](https://www.apimatic.io/pricing): Basic $300/month/language outside offers | Context access is not a reason to upload secrets. Generated SDK license must be checked if adopted. 1–3h | Only claim actual documented context-plugin use; no retrospective claim. No new SDK rewrite justified |
| Render | **CONDITIONAL** judge hosting after local reproducibility | [Sponsor](https://paypalaihackathon.devpost.com/details/render) offers $50 credits. [Pricing](https://render.com/pricing) is resource-based; quote exact compute/DB cost before creation | Account, repo access, DB and secrets required. Cloud cannot reach local loopback Ollama/API. HTTPS cookies/origins + model topology need review. 1–2 days | Deployment/Workflows can add value, but no hosting is mandatory; no deployment approved |
| Elastic | **DEFER** unless audit-search scale becomes real | [Sponsor](https://paypalaihackathon.devpost.com/details/elastic): 14-day Cloud trial, extension request for 30 more days; local option. [Pricing](https://www.elastic.co/pricing) varies by deployment | API key/endpoint and ingestion pipeline; tenant scoping, data minimization and index retention required. License varies by artifact/version, not blanket MIT. 1–2 days | Existing PostgreSQL audit query is enough for this small dataset. No stated standalone Elastic prize found in rules §8 |
| Zapier | **DEFER**, perhaps explicit nonfinancial notification later | [Sponsor](https://paypalaihackathon.devpost.com/details/zapier): new accounts get 14-day Professional trial, then Free. [Pricing](https://zapier.com/pricing): Free 100 tasks/month; MCP limits/task accounting must be separately verified | Account + connected app permissions. Broad MCP financial actions conflict with current boundary; no autonomous payment. 0.5–1 day | Adds third-party data exposure and execution surface; not needed for core story; no standalone prize found in §8 |
| KERNEL | **DEFER**: no browser-agent checkout in trusted payment path | [Sponsor](https://paypalaihackathon.devpost.com/details/kernel): $50 credits. [Pricing](https://www.kernel.sh/pricing): $0 subscription plus usage, $5/month credits, five concurrent browsers on Free | API key/browser session; cloud replay/auth vault can contain secrets. Never bypass authentication or automate approval. 1–2 days | Hosted browser control is unnecessary for the small demo; no standalone prize found in §8 |
| Postman | **P1 small offline collection**, external tooling only after approval | [Sponsor](https://paypalaihackathon.devpost.com/details/postman), [pricing](https://www.postman.com/pricing/): Free $0 core client and 100 AI credits advertised; paid/team limits separate | No credentials needed to author a local redacted collection. Secret environments must never sync publicly; disable automatic financial runs. 1–3h | Useful reproducibility evidence; no standalone Postman prize found in §8 |
| Bryntum | **DEFER**, current project has no scheduling domain | [Sponsor](https://paypalaihackathon.devpost.com/details/bryntum): Gantt/Scheduler/Calendar use. [Store](https://bryntum.com/store): commercial per-product/developer prices and trial; duration/distribution rights need verification | License key and commercial/trial terms, no external API needed for local widgets. 1–2 days | Adding an ornamental timeline is not meaningful scheduling; poor deadline fit |
| Astropods | **DEFER**, retain local controlled orchestration | [Sponsor](https://paypalaihackathon.devpost.com/details/astropods), [pricing](https://astropods.com/pricing): signup credits then usage billing; exact free-credit quantity not published in reviewed page | Account/API token and cloud agent spec. Runtime could receive financial context; explicit privacy approval required. 1–2 days | Duplicates current runtime and widens deployment scope; no standalone prize found in §8 |

Rules §8 identifies named sponsor awards for AG Grid, APIMatic, Bryntum, Channel3
and Render. Being listed as a resource/sponsor is not proof of a separate prize.
Final category/offer interpretation remains with organizers. Do not sign up merely
to collect credits or add logos.

Public `docs.paypal.ai/` and attempted deep links did not resolve reliably during
research. The official PayPal GitHub repositories and developer REST documentation
were usable fallbacks. Channel3's developer page was accessible, but its API-docs
redirect was not fully retrievable; endpoint schemas, normal billing/overage,
request-rate limits, MCP tool scopes and SDK license are **approval-time checks**,
not invented verified facts. Public documentation browsing is distinct from
calling an integration or spending credits.

## Discovery architecture and financial trust boundary

The mission's first gap is real options. Existing extraction explicitly forbids
inventing merchant identity/price and requires financial details in user text.
A search result cannot simply be injected into a prompt and treated as authority.

Proposed future flow, requiring review before backend integration:

1. An authenticated user explicitly requests discovery using a minimal, nonprivate
   query. A server-only Channel3 adapter receives no cookies/financial secrets.
2. Validate a strict normalized quote model: provider product ID, title, retailer,
   amount as Decimal string, ISO currency, optional availability, HTTPS source
   URL and observed timestamp. Missing facts remain null, never synthesized.
3. Set bounded total/connect timeouts, response-size and result-count caps,
   configured request/credit limits, cache TTL and a safe rate-limit error path.
   No automatic generation or paid retry. Reject unsafe URLs, unexpected schemas,
   implausible/ambiguous currency and remote prompt instructions. Do not fetch
   arbitrary URLs or allow SSRF through product/image links.
4. Compare only normalized public facts. User explicitly selects a quote; do not
   let the model create a merchant mapping or financial authorization. Revalidate
   price/availability and disclose staleness before any binding action.
5. A catalog retailer is not necessarily the configured PayPal payee. Without
   independently trusted correspondence, stop at a read-only comparison or
   NEEDS_INFORMATION. A buy link is not a checkout API or proof of PayPal support.
6. Persist quote provenance and authorization scope in a reviewed design before
   linking discovery to payment. Existing proposal schema has no quote reference;
   this requires separately reviewed API/audit changes and possibly a migration.
   Do not silently relax financial grounding or overload the request string.
7. All payment-eligible proposals still traverse deterministic owner/merchant,
   currency, budget and version checks, explicit human review, buyer approval and
   verified capture evidence. Models never receive a capture capability.

A demonstration may show real catalog results and a **separately labeled test
seller Sandbox checkout**. It must not imply that a retailer purchase was fulfilled
or that a catalog merchant accepted PayPal through INTENTRA when that is unverified.

## Controlled execution order and approval gates

### P0 — minimum reliable PayPal + AI submission

1. **Nov 5–6: packaging and evidence.** Review new root README, placeholders,
   observed-version manifests and the offline runner. Owner-approved Apache-2.0 is now installed locally; preserve third-party
   notices and verify recognition after approved publication. Rehearse clean installation in a separate environment; do not migrate
   or reset the existing development database. Estimate 4–8h.
2. **Nov 6–7: recoverability and Sandbox prerequisites.** Review the stale recovery
   revision/fixed IDs with new offline tests; verify merchant and app configuration
   without exposing it. Any provider OAuth/lookup and any stateful integration
   tests need separate approval. Estimate 3–6h.
3. **Nov 7–8: one approved connected rehearsal.** Existing/new test account, one
   trusted test seller, one amount/currency, one approved policy. Execute only
   under explicit operation-by-operation authorization. Show AI result → policy
   ALLOW → owner confirmation → local reservation → buyer checkout → explicit
   capture → verified state/audit. If outcome is uncertain, stop; inspect/reconcile
   the existing attempt instead of creating another. Estimate 4–8h.
4. **Nov 10–11: submission.** Publish reviewed code/license after explicit approval;
   author Devpost description, actual tool list, architecture and limitations;
   record under-three-minute public YouTube footage; verify anonymous judge access
   and prepare an access-maintenance plan. Estimate 4–6h.
5. **Nov 12 by 09:00 Pacific: final checks.** Verify links, source revision, license,
   setup, video and submission receipt. Leave a three-hour buffer before noon.

### P1 — high-value differentiation, only after P0 is secured

- **Discovery:** Channel3 credentials/credit/terms approval, then validated adapter
  and mocked tests; a live public-query test needs explicit approval. 8–16h.
- **Original UI:** warm light surfaces, charcoal/green accent, compact grouped
  navigation; preserve URLs and all one-shot/cancel/payment protections. Prioritize
  Overview, AI Assistant, Approvals, Payments and Spending Policies in small
  reviewable slices. Overview metrics must use existing analytics/proposals/audit
  APIs with unavailable states and per-currency amounts, never fabricated trends.
- **Finance grids:** AG Grid Community for actual owner-scoped transaction search,
  filtering and budgets. Pin compatible package versions; test React 19, keyboard
  focus, overflow, and license notices. Studio/Enterprise requires approved terms.
- **Safe observability:** allowlisted correlation propagation and recovery guidance,
  with no content/token logging. 2–4h.

### P2 — optional, not deadline dependencies

Public landing page, guided synthetic tour, AG Studio agent dashboards, notifications,
Elastic indexing, additional sponsors, and cloud deployment. Synthetic fixtures
must be isolated from live APIs, clearly labeled, never seeded into development
business tables merely by viewing a page. A tutorial may represent Sandbox
states, but a mock cannot be presented as a verified provider transaction.

### Gates requiring explicit approval

- Future license changes (Apache-2.0 is already approved), publication/commit/push, external signup or paid
  credits, SDK/plugin installation broadening tool access, third-party data use.
- Any live inference, proposal creation, account creation, policy approval,
  reservation, checkout/order lookup/authentication, capture or reconciliation.
- Migration/schema changes, production config, service restart, hosting/deployment.
- Hosted credentials must be shared through approved secret management, not a
  public README. Local judges can provision their own Sandbox app and test user.

No gate was crossed by implementing local documentation and an offline runner.

## Smallest coherent demonstration and presentation

Prefer one complete authorization story over a large set of sponsor logos.
For the core entry, explicit purchase details plus real AI extraction are adequate
product scope if accurately described; discovery is not yet a current feature.
If discovery is part of the final claim, implement and verify it or clearly omit it.

Suggested 160-second film: 0–20s audience/problem; 20–40s merchant policy/budget;
40–65s AI proposal and grounded fields; 65–85s owner review; 85–120s genuine
Sandbox buyer approval; 120–145s one explicit capture with server verification;
145–160s audit/budget evidence and limitations. Use actual footage, synthetic
personal details, and explicit Sandbox labels. Do not include credentials or
pretend an edited/mock result is live execution.

## Work completed safely in this pass

- Phase 0 source/rules/sponsor audit, readiness matrix, flow gaps and this plan.
- Root README with exact local setup topology, architecture, guarded demo steps
  and honest discovery/hosting limitations.
- `.env.example` placeholders only; existing secrets were not read or modified.
- API direct-dependency manifests pinned to the installed environment; existing
  `pip check` is clean. No dependencies were installed or model downloaded.
- A bounded selected offline-test runner that refuses network connections/DNS and
  uses an inert process-local database URL; it never starts services.
- No major redesign, new financial API behavior, discovery stub or decorative
  sponsor integration. Sprint 4–11 changes remain intact.

Current test evidence: 183 selected offline Python cases, 17 mocked browser cases,
TypeScript, full ESLint, two proxy wrapper cases and a production webpack build
passed in this session. Stateful database suites were intentionally not run.
See readiness audit for the distinction between present tests, observed historical
records and fresh live verification. Clean installation, sponsor SDK compatibility,
account entitlements, a complete linked Sandbox journey and submission upload
remain verification gates.

### License and final verification notes

The [Ollama runtime license](https://github.com/ollama/ollama/blob/main/LICENSE) is
MIT; the [upstream Qwen3-4B model card](https://huggingface.co/Qwen/Qwen3-4B) declares
Apache-2.0. Verify the exact installed/redistributed model artifact and notices;
these upstream labels do not choose INTENTRA's own license or license SaaS APIs.

After concurrent frontend edits appeared, a source hash snapshot remained stable
through refreshed checks: 17 mocked browser tests, TypeScript, full ESLint, two
proxy tests and the production webpack build passed. These checks used no live
proposal/model/payment API. The local offline runner independently passed all
183 reviewed Python cases with connection and DNS access blocked. Build-generated
include paths were removed without changing earlier sprint configuration.

Workstream A update: Apache-2.0 is now adopted locally for INTENTRA's original
work, with Copyright 2026 Chirag Garg. Root LICENSE matches Apache's official text;
public GitHub recognition still requires approved publication. The
[licensing review](licensing-review.md) records third-party obligations separately.
