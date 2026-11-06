# INTENTRA — hackathon readiness audit

Assessment: 2026-11-05 UTC. Branch: `feature/intent-contract-lifecycle`, HEAD `8f610b3`.
Overall **PARTIAL: not submission-ready**. This is an evidence assessment, not an
eligibility determination, official score, or prediction of a prize.

## Sources, scope, and classification

Primary rules: [official rules](https://paypalaihackathon.devpost.com/rules),
[submission overview](https://paypalaihackathon.devpost.com/), and
[resources](https://paypalaihackathon.devpost.com/resources), checked during this
session. Requirement labels below are a compact checklist; the complete rules
remain authoritative. PASS means observed repository/verification evidence;
PARTIAL means implemented with an important gap; FAIL means a required local
artifact is absent; UNKNOWN requires entrant or external confirmation.

The requested deadline is **November 12, 2026, 12:00 Pacific / 20:00 UTC**.
The five criteria supplied by the user are equally weighted in rules section 6;
none is assigned an invented numerical score here.

No live inference, proposals, confirmations, reservations, provider transactions,
migrations, or database writes were performed. Source inspection, offline tests,
anonymous GitHub metadata, and a read-only aggregate development database query
were used. No personal records, credentials, request text, or model output were
printed. This audit did not start the major frontend redesign. Additional UI changes appeared concurrently and were preserved; see the validation note below.

## Evidence index

Paths below are relative to the repository root; line numbers refer to this audit.

| ID | Repository evidence |
| --- | --- |
| E1 | `apps/api/intentra/services/agent_provider.py:251` Ollama adapter; `:296` payload with `think:false`, 1024-token budget; `:403` feature flags; `:453` read-only status |
| E2 | `apps/api/intentra/services/agent_proposals.py:64` policy; `:154` creation/idempotency; `:303` human confirmation |
| E3 | `apps/api/intentra/services/agent_payment_handoff.py:24` local-only preparation with contract/version/owner checks |
| E4 | `apps/api/intentra/services/paypal_sandbox.py:10` Sandbox endpoint, `:190` OAuth, `:229` order creation, `:353` order lookup, `:432` capture; `provider_runtime.py:17` lazy credential loading |
| E5 | `apps/api/intentra/services/payment_orchestration.py:76` durable order orchestration; `checkout_approval.py:205` server-side buyer-return verification; `payment_capture.py:100` one-time capture claim; `payment_reconciliation_runner.py:38` reconciliation |
| E6 | `apps/api/intentra/services/merchant_registry.py` server-controlled merchant identities; `payment_reservation.py:65`, `payment_execution.py:77`, payment model uniqueness constraints |
| E7 | `apps/api/intentra/routes/auth.py:38`, `:78`, `:133`; `services/auth.py`; `middleware/origin.py`; `main.py` auth, cookies, origins, CORS |
| E8 | `apps/api/alembic/versions/` constraints, ownership, session hashes, append-only proposal/payment event triggers, current head `9d7f1a4c6b20` |
| E9 | `apps/web/src/components/agents/agent-workspace.tsx`, `proposal-card.tsx`, `proposal-detail.tsx`; `src/lib/agents/client.ts` one-shot/cancel handling and actual `proposal_id` |
| E10 | `apps/web/src/app/checkout/{handoff,return,cancel}/route.ts`; `components/payments/payment-workspace.tsx`; approvals, audit, analytics, merchant and status pages |
| E11 | `apps/api/tests/test_paypal_sandbox.py`, `test_agent_provider.py`, `test_authorization.py`, `test_auth_security.py`, `test_merchant_registry.py`, `test_payment_reconciliation.py`; DB-dependent integration tests separately present |
| E12 | `apps/api/scripts/paypal_sandbox_local.py:40`, `:211`, `:222`; `recover_known_paypal_order.py:38`, `:106` launcher and recovery limitations |
| E13 | `compose.yaml`, frontend `package-lock.json`, new root setup guide and API requirements; `apps/api/AI_PROVIDER.md`, `docs/sprint11-ai-workspace.md`, `docs/ollama-generation-diagnosis.md` |

## Mandatory requirement matrix

Rule section numbers map to the primary source above. Effort is an engineering
estimate, excludes organizer review, assumes one experienced contributor, and is
not a promise. Rows describing entrant attestations are not claims about the user.

| Requirement / rule section | Evidence and verified test evidence | Status | Missing / recommended fix | Severity; effort |
| --- | --- | --- | --- | --- |
| PayPal Sandbox + AI centrality (§4) | E1–E6, owner-verified 218 offline-test baseline; historical capture evidence and real Ollama extraction observed separately | PARTIAL | Rehearse one authorized linked journey; demonstrate the real provider path rather than only mocked results | P0; 4–8h plus approvals |
| Stable runnable build (§4) | Owner-verified 35 mocked-browser-test baseline; TypeScript, lint and webpack checks | PARTIAL | Fresh-clone installation and dependency resolution still need verification | P0; 3–5h |
| Declared target platform (§4) | Desktop/mobile web routes; mocked responsive browser evidence | PARTIAL | State supported browser/runtime and hardware prerequisites in submission | P0; 0.5h |
| Working judge access (§4) | Local build exists; setup guide added in this work | PARTIAL | Publish the guide/build after approval and rehearse from a separate checkout; local URLs are not judge hosting | P0; 3–5h |
| Complete public source (§4) | Anonymous GitHub metadata returned 200, public=true for origin | PARTIAL | Sprint 4–11 code and new documentation remain uncommitted/unpublished | P0; 1–2h after review/approval |
| Recognizable OSS license (§4) | Root `LICENSE` contains Apache-2.0; `NOTICE` attributes Copyright 2026 Chirag Garg | PARTIAL | Commit/publish the reviewed files and confirm GitHub recognizes the license; do not infer publication from local files | P0; approval/publication |
| Feature description (§4) | Technical sprint notes exist | PARTIAL | Submit an audience/problem/workflow/limitations description, not only engineering notes | P0; 1–2h |
| Tool disclosure (overview) | Ollama/Qwen3 and direct PayPal HTTP adapter present | PARTIAL | List actual versions and roles; do not claim toolkit/sponsor usage not implemented | P0; 0.5h |
| Public YouTube link (§4) | No project video/link found in repository evidence | UNKNOWN | Record, upload, and verify anonymous access; external artifact may exist outside this workspace | P0; 3–5h |
| Concise functional footage (§4) | Screenshots and tests exist, not a submitted film | UNKNOWN | Target 150–170 seconds of actual operation with truthful labels | P0; included above |
| Media permissions (§4, §7) | No rights inventory or final media supplied | UNKNOWN | Use original copy/visuals; review music, marks, screenshots and third-party material | P0; 0.5–1h |
| In-period development (§4) | 23 commits dated Oct 31–Nov 3, plus uncommitted sprint work | PARTIAL | Explain substantive changes and publish a reviewable change summary | P0; 0.5h |
| Integration/license permission (§4) | Existing dependencies; no complete notices inventory | PARTIAL | Review SDK/model/runtime licenses and service terms before redistribution or new integrations | P0; 1–2h |
| Original ownership (§4, §7) | Source attribution/ownership attestation not in repo | UNKNOWN | Entrant confirms rights and compliant dependency use | P0; owner attestation |
| English materials (§4) | Existing documentation/UI are English | PARTIAL | Check final video and Devpost form too | P0; 0.5h |
| Testing continuity (§4) | Local access depends on developer machine; no access runbook | PARTIAL | Maintain judge access through Dec 15, 2026, 08:00 Pacific; supply safe access instructions without publishing real secrets | P0; 1–2h + operations |
| Registration and final form (§4) | Cannot inspect entrant's Devpost dashboard | UNKNOWN | Entrant confirms registration, required fields, links, and receipt before deadline | P0; 0.5–1h |
| Age/residency/conflicts (§3) | Not inferable from code | UNKNOWN | Entrant reviews eligibility, exclusions and relationships against full rules | P0; owner attestation |
| Authorized representative (§3, §4) | Team/organization status unknown | UNKNOWN | Identify authorized submitter where applicable | P0; owner attestation |
| Distinct multiple entries (§4) | Other submissions unknown | UNKNOWN | Compare entries if submitting more than one | Conditional P0; owner review |
| Support/conflict restrictions (§4) | Funding/contract history unknown | UNKNOWN | Entrant confirms permitted support history | P0; owner attestation |
| Entry conduct/consents (§7–15) | Cannot be established by tests | UNKNOWN | Review rights, publicity, forms, privacy, dispute and administrative obligations; obtain clarification where needed | P0; owner review |
| Sponsor-specific conditions (§8) | No optional sponsor integration evidenced | UNKNOWN | Claim a sponsor category only after implementing and documenting qualifying use | Conditional; see master plan |
| Submission freeze (§5) | No submitted release/receipt inspected | UNKNOWN | Entrant freezes the reviewed submission before cutoff and checks permitted correction rules | P0; 0.5h |
| Benign submission content (§7) | No formal dependency/malware assessment performed | UNKNOWN | Review artifacts and attest to permitted, nonmalicious content | P0; owner review |
| Special hardware access (§4) | Ordinary web/local model setup; no proprietary hardware integration found | PASS for current architecture | Disclose model resource requirements; reassess if hardware changes | Low; 0.5h |

Public hosting and a specific AI sponsor are not prerequisites for the core
submission. A local setup path must actually be reproducible. The matrix does not
recommend real-money transactions; the implemented payment endpoint is Sandbox.

## Current state: read-only aggregate evidence

Development database identity was explicitly checked as `intentra`; migration
revision matched the single repository head `9d7f1a4c6b20`. Queries ran with
`SET TRANSACTION READ ONLY` and selected no raw provider responses or secrets.

| Observed record grouping | Count |
| --- | ---: |
| OLLAMA DRAFT, no policy result | 1 |
| OLLAMA NEEDS_INFORMATION, matching policy decision | 1 |
| SIMULATED CONFIRMED, policy ALLOW | 1 |
| PENDING payment, no order/capture ID | 1 |
| SUCCEEDED payment, order and capture IDs present | 1 |
| EXECUTION_PENDING reservation | 1 |
| CAPTURED reservation | 1 |
| APPROVED checkout evidence with verification timestamp | 1 |
| CAPTURE_COMPLETED events | 1 |

These records support **historical recorded success**, not a fresh provider
verification in this audit. They do not establish that the successful capture
belongs to the current OLLAMA proposal. That proposal is intentionally incomplete
and has no approved contract. A pre-existing pending attempt must be reviewed
before any future demonstration; creating another order is not a recovery strategy.

## End-to-end gap analysis

| Stage | Implemented behavior / evidence | Status and gap |
| --- | --- | --- |
| Request + extraction | E1, E9: authenticated one-shot POST, strict schema, finite timeout and response caps; historical live extraction completed in 9.783s and proposal test in ~9s | PASS for existing explicit-detail extraction; not product discovery |
| Product discovery | No Channel3/catalog adapter, query endpoint, quote provenance, or product comparison contract found | FAIL against the proposed discovery story; optional for core hackathon eligibility. Do not advertise it as implemented |
| Deterministic policy | E2: owner scope, merchant/currency/amount, approved contract/version, remaining budget; money uses Decimal | Implemented; unit tests pass. DB concurrency/owner-isolation tests exist but were not rerun because they write |
| Human confirmation | E2, E9, E10: separate explicit action, only ALLOW + READY_FOR_REVIEW, current contract/version checked | Implemented; simulated browser regression passes. Not demonstrated here with a payment-eligible real Ollama result |
| Reservation + attempt | E3, E6: confirmed eligible proposal only, locks and uniqueness, atomic handoff, no provider call | Implemented; integration tests present but skipped; pending historical record requires review |
| Provider order + checkout | E4, E5: real OAuth and Orders API, sandbox URL allowlist, explicit payee, persisted request ID and durable claims; 20s frontend handoff timeout | Real code, not a mock-only adapter; current credentials/account mapping and new complete journey not externally verified |
| Buyer-return verification | E5, E10: hashed one-time state, expiry, actor/contract/order/merchant/amount/currency checks and server order GET | Implemented; historical verified evidence present, mocked client/adapter coverage. Never trust browser query success |
| Capture + uncertainty | E5: persisted capture claim and independent idempotency key; uncertain state reserves budget; terminal result requires validated provider evidence | Implemented; offline adapter/planner tests pass; stateful capture/reconciliation tests not rerun |
| Reconciliation + recovery | GET existing order and validate evidence, no automatic repeat capture; local DB reconciliation writes only on explicit action | Implemented but recovery helper pins old schema revision and fixed known-order context. Operational readiness PARTIAL |
| Audit + budget effects | E8 append-only event triggers; E10 owner-scoped audit and currency-specific analytics | Historical evidence present; live request-to-event correlation is incomplete in the current temporary sanitized-log wrapper |

## Five judging criteria: evidence-based assessment

The following are internal assessments, not official scores.

| Criterion | Assessment | Strengths | Weaknesses and concrete next step |
| --- | --- | --- | --- |
| Technological Implementation | PARTIAL | Non-trivial direct PayPal API client; server verification; durable create/capture claims; uncertainty-aware budget retention; local structured AI | Show one linked Sandbox journey and a clean setup. Keep deterministic authorization outside models; verify account/mapping and recovery compatibility before demonstrating |
| Design | PARTIAL | Responsive shell, optional-contract composer, stopped-waiting semantics, persisted detail page, accessible labels and empty/error states; owner-verified 35 mocked-browser-case baseline | Workflow crosses Agents → Approvals → Payments; older Overview emphasizes payments and has incomplete AI activity/budget context. Prioritize a coherent journey and consistent labels before broad redesign |
| Potential Impact | PARTIAL | Bounded AI purchasing addresses a credible authorization-risk problem | Audience, interview evidence and measured outcomes absent. Pick a specific operations/procurement user; show a blocked out-of-policy request and explain the prevented failure without inventing savings |
| Innovation / Idea | PARTIAL | Separating untrusted extraction, policy, human confirmation, provider evidence and unknown-state recovery is a useful differentiator | No comparative product evidence or actual shopping discovery. Explain this boundary architecture rather than claiming world-first autonomy |
| Presentation | PARTIAL; submission artifacts incomplete | Existing working AI result, traceable states, synthetic screenshots and architecture suitable for a short story | Public video, pitch and frozen judge runbook unverified. Record real operation, label mock/Sandbox boundaries, show the audit and one failure state |

## Security and operational findings

1. **P0 — license publication + release packaging.** Apache-2.0 and a project
   NOTICE now exist locally. Current uncommitted changes are invisible to judges
   until separately approved publication. Never push local secret files.
2. **P0 — recovery helper compatibility.** E12's recovery script requires
   `f1a2b3c4d5e6`, while the database/launcher head is `9d7f1a4c6b20`. It will refuse
   the current schema. It also targets a specific known recovery context, so do
   not present it as a generic judge workflow. Fix with offline regression and
   explicit review; do not weaken its guard during this audit.
3. **P0 before hosting — auth/origin configuration.** Session cookies are HttpOnly
   and hashed server-side, but `secure=False` is intentionally local HTTP. Login
   has no observed rate limiter. Allowed origins and proxy API target are local.
   Hosted access needs reviewed HTTPS cookies, origins, secrets and abuse controls.
   A hosted frontend cannot use the user's loopback API/Ollama automatically.
4. **P1 — mapping is configuration, not retail proof.** The merchant registry is
   server-controlled and rejects missing/duplicate mappings. Configuration alone
   does not establish that an arbitrary catalog retailer accepts this PayPal flow.
5. **P1 — no asynchronous provider event ingestion found.** Manual order lookups
   and explicit reconciliation exist; webhook ingestion was not found. This is
   not a universal hackathon requirement. Describe the current supported behavior.
6. **P1 — correlation gaps.** Source diagnostic context has a correlation ID, but
   the existing temporary sanitized-log formatter omits it. Proposal audit event
   correlations are per-event UUIDs, not the browser request ID. Add tested safe
   UUID propagation in a separately scoped change; do not log credentials/content.
7. **P1 — bounded but long waits.** Global Next rewrite timeout is 330s, while
   Ollama defaults to 120s and permits 300s. This is an inactivity setting, not a
   global concurrency or wall-clock guarantee. Acceptable controlled local demo;
   review a proposal-only total deadline before broad exposure.
8. **P1 — model/SDK notices.** Review the installed model artifact license and
   third-party dependencies; do not assume INTENTRA's Apache-2.0 license licenses
   hosted services, commercial grids, model weights, or third-party media.

## Validation performed and deliberately skipped

- **Owner-verified baseline: 218 offline Python tests passed**, with socket connection/DNS access blocked
  in the runner and a dummy database URL. Includes agent adapter/failure route,
  authorization, password/session helpers, registry, reconciliation planner,
  mocked PayPal adapter, launcher migration-head check and local recovery config.
- **Owner-verified baseline: 35 mocked frontend tests passed** on the current reviewed implementation;
  API requests were intercepted. TypeScript and full ESLint passed.
- **Two proxy wrapper tests passed**. Previous Sprint 4 real-transport results are
  historical evidence; actual 330-second expiry/load testing was not rerun here.
- **Production webpack build passed**, 19 static pages plus dynamic detail shell.
  Default Turbopack had an environment IPC/port-binding limitation in prior checks.
- `pip check` found no broken requirements in the existing virtualenv. No clean
  dependency installation was performed; new manifests pin observed direct deps.
- Historical audit GitHub metadata: public=true, license absent before local adoption.
  Current public Apache-2.0 recognition is unverified until approved publication. No provider
  credentials were used. No secret-named files were tracked by the filename check;
  this is not a complete history/content secret audit.
- Current database evidence was queried read-only, not generated during the audit.
- Database-writing integration suites, checkout return flows, actual provider API
  validation, fresh model inference and new proposals were **not run**. Their
  presence in source is not counted as a passing live or stateful integration test.

## Prioritized delivery plan

See [master plan](hackathon-master-plan.md) for sponsor selection and approval gates.

| Priority | Work | Estimate | Done when |
| --- | --- | --- | --- |
| P0 | Publish reviewed Apache-2.0 license, source and runbook | 2–4h | Anonymous clone exposes license and all actual sprint source |
| P0 | Reproducible install and safe configuration | 3–5h | A second checkout runs with documented local model and Sandbox prerequisites |
| P0 | Review recovery helper/current merchant & Sandbox setup | 2–4h | Revision guard has tests and a safe recovery plan; no unresolved order is retried |
| P0 | Separately authorized end-to-end rehearsal | 4–8h | One owner-approved Sandbox journey has matching amount, payee, policy, capture evidence and audit |
| P0 | Submission artifacts and access maintenance | 4–6h | Working build/setup, description, tool list, public video, change summary, access checks and submission receipt |
| P1 | Narrow original UI polish, actual metrics, workflow labels | 6–10h | Overview and AI journey communicate current capabilities without fake totals |
| P1 | Channel3 read-only discovery, if approved | 8–16h | Grounded quotes, provenance and expiry, external-spend consent, mocked tests; unverified merchants remain blocked |
| P1 | Safe observability and recovery guidance | 2–4h | Request/event linkage and uncertain-state operator instructions are reproducible |
| P2 | Community grid, synthetic guided tour, exportable evidence | 4–8h each | Real usefulness, license and privacy verified; no auto financial mutations |
| P2 | Broad visual redesign or additional sponsors | Unbounded if uncontrolled | Deferred unless all P0 work is complete |

Recommended next sprint: **submission foundation + reproducible Sandbox rehearsal**,
not a wholesale redesign or general autonomous shopping agent. The smallest
credible demonstration is one local AI extraction, one approved merchant policy,
one explicit human review and Sandbox checkout/capture, then matching audit and
budget effects. Product discovery is a separate currently missing capability;
if omitted, the pitch must say extraction rather than claiming discovery.

### Shared-workspace qualification

Additional edits to frontend typography, Overview, shell and UI primitives, plus
an API environment example, appeared during this work. They were not authored or
reverted by this audit. Baseline browser/build evidence initially described the
Sprint 11 snapshot; current-source checks were refreshed afterward. Setup files
added here improve packaging but do not establish a completed clean-clone install
or update the public repository without a separately approved publish.

Historical refreshed validation after those concurrent edits reported 35 mocked
browser cases, TypeScript, ESLint, two proxy tests and production webpack build.
A frontend source fingerprint was unchanged across that validation window. Prior
sprint source, payment behavior, financial records and service processes were
preserved.

## Sprint 13 release gates

| Priority | Remaining task | Dependency / proof of completion |
| --- | --- | --- |
| P0 | Commit and publish reviewed source, `LICENSE`, `NOTICE`, README, and runbooks | Owner approval; anonymous GitHub clone shows Apache-2.0 recognition and no secrets. |
| P0 | Execute the separately approved minimal Sandbox rehearsal | Dedicated Sandbox identities, disposable DB, single USD 0.01 plan, redacted captured evidence. |
| P0 | Finalize judge access and submission artifacts | Stable judge run instructions or approved hosting, public video under three minutes, Devpost form and owner attestations. |
| P0 | Clean-clone rehearsal on the intended judge platform | Python package access/mirror, `npm ci`, no hidden local database/model/service dependency. |
| P1 | Produce a full transitive dependency lock/wheelhouse | Platform-aware lock review; retain the direct manifests for human readability. |
| P1 | Close recovery-helper disposition | Retire/quarantine the historical helper or design a separately reviewed current-head recovery path; never weaken its guard. |
| P1 | Perform visual responsive review | Manual desktop/mobile screenshots of payment/approval/history routes; mocked browser tests cover agent workspace but not all payment screens. |

The local Apache-2.0 files satisfy the source-tree artifact requirement, but
publication and GitHub recognition remain unverified until the owner approves a
commit/push. See [Sandbox demo runbook](paypal-sandbox-demo-runbook.md) for the
connected-flow trace and approval boundaries.

## Workstream A — Apache-2.0 adoption

The owner explicitly approved Apache License, Version 2.0. Local license selection
is resolved: root LICENSE contains the complete official, unmodified text; README
and NOTICE use **Copyright 2026 Chirag Garg**. Publication/GitHub recognition is a
separate pending gate. See [licensing review](licensing-review.md) for the 474-entry
JavaScript lockfile review, Python metadata review, bundled notices, and outstanding
LGPL/MPL/attribution and template-branding distribution checks. No third-party
material was relabeled as INTENTRA-owned code, and no runtime/payment behavior
changed. Git tracking is verified separately from public publication.
