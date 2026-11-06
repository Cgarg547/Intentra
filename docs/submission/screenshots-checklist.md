# Screenshot checklist

- Dashboard: show the workflow hierarchy; label any demo financial data.
- AI Agents: show request source (`Local Ollama` or `MOCK`) and proposal state.
- Contract and policy: show a synthetic merchant, USD 0.01 limit and ALLOW only
  if it is a real persisted result.
- Human approval: show the explicit confirmation boundary.
- Payment workspace: show Sandbox labeling and state, never claim capture from a
  browser redirect alone.
- Audit Explorer: show the correlated transition sequence, with IDs truncated.
- PayPal screen: only a Sandbox buyer screen, with personal/buyer data redacted.

Before export, redact client secrets, access tokens, authorization headers,
session cookies, personal emails/names, full merchant IDs, provider IDs, local
paths and browser extensions. Do not manufacture screenshots or edit a mock
state to look provider-verified.
