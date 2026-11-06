# 160-second demo script and recording plan

Only record screens actually shown. Apply a visible `MOCK` label to intercepted
API flows and `PayPal Sandbox` to provider screens. Hide passwords, cookies,
tokens, buyer details, full merchant IDs and full provider IDs.

| Time | Screen | Narration |
| --- | --- | --- |
| 0–15s | Dashboard / workflow overview | “INTENTRA is human-governed purchasing for AI agents. The model can structure a request, but it never authorizes spend.” |
| 15–37s | AI Agents request and result | “Here an agent extracts only the facts supplied in a request. This recording labels the source as Local Ollama or Mock. It is not product discovery.” |
| 37–58s | Proposal policy explanation | “The server evaluates the approved contract, merchant, currency, amount and remaining budget deterministically. An allowed result is still not a payment.” |
| 58–78s | Approvals / confirmation | “A human owner reviews and explicitly confirms the proposal. Contract and policy versions are rechecked before preparation.” |
| 78–101s | Payments preparation / audit | “Confirmation creates a controlled reservation and durable payment attempt. Idempotency prevents duplicate provider submissions.” |
| 101–123s | Checkout handoff | “For this approved recording, this is PayPal Sandbox—not a live payment. The buyer approves one Sandbox order, then INTENTRA verifies the existing order server-side.” |
| 123–142s | Capture and result | “Capture is a separate, one-time action. A browser return alone is never accepted as success; provider payee, amount and currency must match.” |
| 142–160s | Audit Explorer / unknown state | “The audit trail shows the boundaries. If the provider outcome is uncertain, INTENTRA holds the reservation and reconciles the existing order instead of retrying blindly.” |

Do not splice mock policy results together with an unlabeled real provider claim.
If no authorized Sandbox capture is recorded, end after the mock/implementation
walkthrough and say that live provider proof is not included.
