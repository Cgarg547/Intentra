# INTENTRA final hackathon checklist

Assessment date: 2026-11-06. Repository evidence only unless a row names a
local command result. This checklist supersedes neither the organizer rules nor
owner attestations. `PASS` means locally evidenced; `PARTIAL` means implemented
but missing release evidence; `UNKNOWN` needs an external or owner action.

| Priority | Item | Status | Evidence / required follow-up |
| --- | --- | --- | --- |
| P0 | Safe AI-to-payment boundary | PASS | Local Ollama extraction is separated from deterministic contract/policy checks, explicit confirmation, reservation, provider verification and capture claims. See `README.md` and API services. |
| P0 | PayPal Sandbox implementation | PARTIAL | Direct OAuth/Orders adapter and offline tests exist. A current linked Sandbox journey is not evidenced in this pass; do not present mocks as provider proof. |
| P0 | No duplicate/ambiguous provider retry | PASS (218 offline tests) | Durable create/capture ids, validation and unknown-outcome reconciliation are covered by the verified selected offline suite. |
| P0 | Sandbox demo rehearsal | UNKNOWN | Requires owner approval for disposable DB writes, provider OAuth, one order, buyer approval and separate capture. |
| P0 | Public source and Apache-2.0 recognition | PARTIAL | `LICENSE` and `NOTICE` are tracked locally. Commit/push/public GitHub verification require owner approval and were not performed. |
| P0 | Submission video and Devpost | UNKNOWN | Scripts/checklists are present under `docs/submission`; recording, upload, fields, eligibility, and receipt are owner actions. |
| P0 | Judge setup / public access | PARTIAL | Local setup and safety limits are documented; no hosted judge environment or fresh-clone rehearsal is evidenced. |
| P1 | Frontend journey clarity | PASS (35 mocked Playwright tests) | The verified mocked browser suite passed 35 tests. Workspace navigation includes contracts, AI agents, approvals, payments and audit; Sandbox and mock boundaries are labeled. This is browser-regression evidence, not PayPal provider proof. |
| P1 | Session/origin production posture | PARTIAL | Local cookie is HttpOnly/Lax but intentionally `secure=False`; CORS/origins and loopback proxy are local-development defaults. Production needs HTTPS, reviewed origins, secret management and abuse controls. |
| P1 | Dependency reproducibility | PARTIAL | Node lockfile and pinned direct Python requirements exist. Python transitives are not hash-locked; fresh installation needs registry/mirror access. |
| P1 | GitHub Actions | PARTIAL | Workflow runs offline API checks and web type/lint/proxy checks on Python 3.14 / Node 22. Remote execution was not claimed or observed. |
| P1 | Legacy recovery helper | PASS (quarantined) | `recover_known_paypal_order.py` remains excluded from demo/setup and guarded for an old revision. Do not enable, alter, or run it. |
| P2 | Optional product discovery claims | FAIL (not implemented) | There is no catalog/product-discovery integration. Describe AI extraction of explicit user details only. |
| P2 | Release notices / third-party artifacts | PARTIAL | Apache `LICENSE`/`NOTICE` are present; a distribution-specific notice inventory remains needed for binaries, images, model artifacts or media. |

## Safe release gate

Local engineering is conditionally ready for review once the verification
commands in `README.md` pass. Submission is **not ready** until the P0 external
items have evidence: authorized Sandbox rehearsal, public source/license check,
public video/Devpost completion, and owner eligibility/access attestations.

## Explicitly approval-gated work not performed

- Database creation, migrations, writes, service start/restart, live Ollama use.
- PayPal OAuth/API calls, order creation, buyer checkout, capture or reconciliation.
- Commit, push, deployment, public source publication, Devpost or YouTube actions.
