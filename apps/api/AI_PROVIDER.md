# Purchase planning model configuration

Purchase planning defaults to the local deterministic provider. Provider choice
is explicit through `AGENT_AI_PROVIDER`: `mock`, `openai` (legacy `llm` alias),
or `ollama`. Selecting OpenAI or Ollama requires `AGENT_LLM_ENABLED=true`; a
disabled or invalid selection fails closed instead of silently selecting a
different provider.

| Setting | Required value |
| --- | --- |
| `AGENT_LLM_ENABLED` | `true` |
| `AGENT_AI_PROVIDER` | `llm` |
| `INTENTRA_LLM_BASE_URL` | HTTPS OpenAI-compatible API base URL (for example, ending in `/v1`) or a full Chat Completions endpoint |
| `INTENTRA_LLM_MODEL` | Model name accepted by that endpoint |
| `INTENTRA_LLM_API_KEY` | Provider credential, supplied only through the API process's secret manager/environment |

For local Ollama, set `AGENT_AI_PROVIDER=ollama`,
`AGENT_LLM_ENABLED=true`, and `INTENTRA_OLLAMA_MODEL=qwen3:4b`
(the default if absent; an empty value is invalid). `INTENTRA_OLLAMA_BASE_URL` is optional and defaults to
`http://127.0.0.1:11434`. The API rejects non-loopback URLs and bypasses proxy
environment variables for Ollama requests. No Ollama API key is used.

System Status reports provider selection, configuration, runtime availability,
and whether the configured Ollama model is present. Its Ollama availability
check is a bounded, read-only `GET /api/tags`; it does not load or execute a
model. OpenAI availability is not probed.

For local development, keep `AGENT_LLM_ENABLED=false` or set
`AGENT_AI_PROVIDER=mock`. Restart the API process after changing its
environment. Do not set these values as `NEXT_PUBLIC_*` variables and never
put the API key in frontend configuration.

The adapter sends only the user's purchase-request text (up to 4,000
characters) to the configured model. Do not include passwords, payment
credentials, session tokens, or unrelated sensitive personal information.
The OpenAI adapter requests JSON containing `purpose`, `merchant_id`, `amount` as a
decimal string, and `currency`. It rejects unknown fields, invalid monetary
precision, unsupported or request-ungrounded financial details, malformed
responses, and responses exceeding the configured size or time limits.

The Ollama adapter requests non-streaming JSON constrained by a schema and
applies the same Pydantic and request-evidence validation. It bounds the model
context, output length, response size, and request timeout.

Model output is untrusted proposal data. INTENTRA independently applies the
owner's selected contract, trusted merchant registry, supported-currency
rules, budget, and human-confirmation requirements. The model has no PayPal
credentials and cannot create reservations, orders, approvals, or captures.

Configuration readiness is not provider-availability verification. INTENTRA
does not issue a model health-check request at startup or as part of this
configuration flow. No live model request is made by the test suite.

## Sprint 5.8 limits and local verification

`INTENTRA_OLLAMA_TIMEOUT_SECONDS` defaults to 120; accepted values are finite,
1–300 seconds. A total deadline bounds slow responses. `localhost` is pinned
to 127.0.0.1; cloud-suffixed model names are rejected. `keep_alive=0` requests
unloading after inference. All four output keys are required; unknown values
must be null. Unsupported structured output fails closed without fallback.

System Status model presence verifies installation, not successful inference.
The development database is reported at revision `9d7f1a4c6b20`; no migration
is needed for this activation. Verify the revision independently before enabling
proposal traffic.

### Separately approved smoke test — NOT RUN

Assumes the existing daemon is running. The Python command loads and runs the
model; neither command starts services, installs models, or uses the database.

```sh
curl --noproxy '*' --max-time 3 --fail http://127.0.0.1:11434/api/tags
cd /Users/Chirag/Desktop/intentra/apps/api
AGENT_AI_PROVIDER=ollama AGENT_LLM_ENABLED=true INTENTRA_OLLAMA_MODEL=qwen3:4b INTENTRA_OLLAMA_BASE_URL=http://127.0.0.1:11434 INTENTRA_OLLAMA_TIMEOUT_SECONDS=120 .venv/bin/python - <<'PYTEST'
import asyncio
from intentra.services.agent_provider import get_purchase_planning_provider

async def main():
    result = await get_purchase_planning_provider().extract(
        "Buy a replacement keyboard from merchant id office_store for USD 20.00"
    )
    print(result.model_dump_json())

asyncio.run(main())
PYTEST
```
