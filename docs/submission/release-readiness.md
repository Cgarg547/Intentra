# Release readiness evidence — 2026-11-06

This is an evidence ledger, not a claim of publication, hosting, a provider
transaction, or final Devpost submission.

| Area | Status | Evidence / boundary |
| --- | --- | --- |
| Core local workflow | PASS (source reviewed) | Owner-scoped contracts, proposals, confirmation, reservations, attempts, checkout verification, capture claims and audit routes exist in the checked-out source. |
| Payment safety | PASS (offline baseline) | Current verified baseline: 218 selected backend offline tests. Unknown outcomes retain holds; no automatic retry is permitted. |
| Web journey | PASS (mocked baseline) | Current baseline: 35 mocked Playwright cases, plus TypeScript, ESLint, proxy and webpack build checks reported by the owner. Mocked UI is not provider evidence. |
| Controlled Sandbox demo | UNKNOWN | Requires separately approved disposable-DB writes, service start, OAuth, order, buyer approval, and separate capture. See [../paypal-sandbox-demo-runbook.md](../paypal-sandbox-demo-runbook.md). |
| Fresh-clone rehearsal | PARTIAL | On 2026-11-06, a separate local clone of committed HEAD passed frontend `npm ci`, TypeScript, ESLint, offline proxy tests (2/2), and isolated webpack build. Backend install, browser, database and provider paths remain unverified in the clone. |
| Public source and license | PARTIAL | Apache-2.0 `LICENSE` and `NOTICE` are local tracked files. Commit, push and public GitHub recognition are owner-gated and not performed. |
| Video, Devpost, receipt | UNKNOWN | Drafts and checklists exist. Upload, final form, eligibility attestations and receipt remain owner actions. |
| Production posture | PARTIAL | This is a local prototype. HTTPS, secure cookies, production origins, secret management, availability, abuse controls and operational monitoring need independent production review. |

## Go/no-go

The codebase is ready for a **controlled, owner-approved Sandbox rehearsal**,
subject to the runbook prerequisites. It is **not yet ready to represent as a
publicly submitted hackathon entry**, because no public source verification,
video URL, Devpost receipt, fresh-clone rehearsal, or current linked Sandbox
evidence is available in this workspace.

## Official rule cross-check — 2026-11-06

The current [official Devpost rules](https://paypalaihackathon.devpost.com/rules)
state a November 12, 2026, 12:00 PM Pacific deadline and require a project with
PayPal developer-platform/Sandbox integration central to an AI-enabled project,
a functional demo judges can run or interact with, a public open-source
repository whose license is visible/detectable, and a public YouTube demo under
three minutes showing the project functioning. The rules also require English
materials, original/authorized work, and entrant eligibility/representation
attestations.

INTENTRA's current materials align with the intended local-setup and under-three-
minute-video paths, but none of the following is yet externally verified: public
repository/license recognition, working fresh-clone judge rehearsal, public
video, final Devpost form/receipt, owner eligibility, or a linked current
Sandbox journey. Do not include private PayPal credentials, buyer credentials,
or private database access in judge instructions; offer only a safe mock/offline
path unless the owner creates a disposable, revocable judge-access plan.
