# Ollama generation diagnosis (offline)

Checkpoint: `8f610b3`, branch `feature/intent-contract-lifecycle`.

The initial sections describe the pre-fix adapter and offline investigation.
The Sprint 7 section below records the subsequent authorized live diagnostic
and current request settings.

## Findings

The original failure cannot be uniquely identified from the supplied event history.
`PROPOSAL_GENERATION_FAILED` stores provider mode but not the error code. A DRAFT
with that event and no evaluation is consistent with the handled failure path.
The approximately 44-second interval does not distinguish invalid output, network
failure, or a configured timeout. Runtime model availability does not establish
that extraction succeeded.

There is a demonstrated proxy deadline mismatch. Installed Next.js 16.4.3
`dist/server/lib/router-utils/proxy-request.js` uses a 30,000 ms default and writes
500 on proxy transport errors. Ollama defaults to a 120-second deadline and allows
up to 300 seconds. A proxy can therefore stop waiting before the API returns its
handled 503. The minimal fix sets `experimental.proxyTimeout` to 330,000 ms.
This is a plausible explanation for the browser symptoms, not proof of the
historical connection reset's source. No running server was restarted.

## Exact request and validation contract

The adapter sends one POST to the loopback `/api/chat` endpoint, with no auth,
tools, redirects, environment proxy routing, or retries. `localhost` is pinned to
127.0.0.1. Its JSON body contains:

- `model`: configured `INTENTRA_OLLAMA_MODEL`, default `qwen3:4b`.
- `stream: false`, `keep_alive: 0`.
- `options: {temperature: 0, num_predict: 300, num_ctx: 4096}`.
- `format`: `ExtractedPurchase.model_json_schema()`, amended to require all four
  fields and forbid extra properties. Amount is a string matching
  `^[0-9]+(?:\.[0-9]{1,2})?$` or null. Currency has `^[A-Z]{3}$` and allows null.
- A system message requiring explicit purchase detail extraction only and a user
  message containing the first 4,000 characters of the request. The exact system
  message is in `OllamaPurchasePlanningProvider.extract`.

The parser reads at most 32,000 decoded response bytes, requires a JSON envelope
with string `message.content` of at most 8,000 characters, and parses that string
as a JSON object with exactly purpose, merchant_id, amount, and currency. It does
not strip markdown fences or use `message.thinking`. Amount must be a decimal
string or null; Pydantic requires positive finite amounts with at most two decimal
places. Purpose and merchant ID have 500/128-character limits. Currency must be
three uppercase ASCII letters. Financial values and merchant IDs must also be
explicitly grounded in the request. Missing values use null.

There is no explicit `think` setting. A thinking-only or token-truncated response
is rejected safely in offline tests. Exhaustion of the 300-token budget is a
candidate explanation, but changing thinking behavior or token limits is not
justified by the available evidence. `done_reason` is not currently inspected.

The adapter has both an asyncio total deadline and HTTPX timeout using the
configured duration (default 120 seconds, accepted range 1–300); connect timeout
is capped at two seconds. HTTP 404 maps to `OLLAMA_MODEL_UNAVAILABLE`, >=500 to
`OLLAMA_PROVIDER_ERROR`, and other non-success statuses to
`OLLAMA_REQUEST_REJECTED`. Invalid output maps to `OLLAMA_INVALID_RESPONSE`,
deadline expiration to `OLLAMA_TIMEOUT`, and transport errors including resets
to `OLLAMA_UNAVAILABLE`. Exceptions do not expose provider bodies.

## API and middleware behavior

`agent_proposals.create_proposal` persists DRAFT and PROPOSAL_CREATED before
extraction. On validation/provider failure it records PROPOSAL_GENERATION_FAILED,
increments the version, leaves DRAFT, and raises sanitized AgentProposalError
with status 503 before evaluation. Persistence exceptions can instead propagate
as 500. The agents route converts the handled error to HTTPException(503).
An offline ASGI test with the service mocked confirms that the actual app's
origin/CORS middleware preserves this status and safe detail. No database is
used by that test.

`provider_runtime.py` builds PayPal checkout providers only; it is not part of
Ollama extraction. It was inspected but not invoked. The browser agents client
retains the HTTP response status and has no explicit fetch deadline.

Diagnostics log structural metadata, timing, stage, safe error code, and a
request-scoped correlation ID rather than request/model text. The helper trusts
callers to supply safe fields; it does not enforce a field allowlist itself.
Generic invalid-output diagnostics do not currently distinguish token exhaustion
from other malformed content. No speculative parser or logging changes were made.

## Offline verification

From `apps/api`:

```sh
DATABASE_URL=postgresql+asyncpg://offline:offline@127.0.0.1:1/offline .venv/bin/python -m pytest -q tests/test_agent_provider.py tests/test_agent_failure_offline.py
```

Result: 78 passed. HTTPX MockTransport covers extraction; dependency overrides
and a mocked service cover API failure routing. Database integration tests were
not run. The dummy URL avoids loading development credentials and is never used
to connect.

From `apps/web`:

```sh
node --test tests/proxy-offline.test.cjs
npx --no-install eslint next.config.ts tests/proxy-offline.test.cjs
```

Result: two proxy tests passed; focused ESLint passed. Tests execute the installed
Next proxy function with its transport replaced, open no sockets, reproduce the
500 error branch and original default timeout, and check the configured deadline.
The success fixture supplies an upstream 503; this is not a live network test.
The deadline regression test failed before the configuration change.
`git diff --check` passed.

## Next safe verification

Inspect existing sanitized application logs for `proposal_generation_failed`
and its error_code, plus `ollama_response_received` metadata, correlated to the
failed request. Do not replay it or collect raw model/user bodies. Under the
current safety constraints no live generation, database inspection, migration,
payment operation, or service restart was performed. A future end-to-end check
of the timeout change requires separate authorization to reload the web service
and exercise generation; it is outside this offline diagnosis.

## Sprint 4 real transport verification

`apps/web/tests/proxy-transport.test.cjs` adds isolated synthetic HTTP servers
bound to 127.0.0.1 on OS-assigned ephemeral ports. It calls the installed Next.js
16.4.3 `proxyRequest` entry point used by external rewrites, with its real bundled
httpxy transport. No transport, socket, or timer is replaced. The harness does
not start Next's full routing server or contact the configured API destination.
Only expected synthetic console errors are suppressed. It checks allocated ports
against the prohibited service ports and closes servers, sockets, and delayed
response timers after each test.

The sandbox initially denied socket listeners with EPERM. The exact test command
was then run with approved local socket access and all five tests passed:

| Case | Observed result |
| --- | --- |
| Synthetic upstream 503 | Status, sanitized JSON body, and content type forwarded unchanged |
| Silent upstream for 31,250 ms | 503 forwarded after approximately 31.27 seconds with the configured 330,000 ms timeout |
| Idle upstream with a test-only 100 ms timeout | Generic 500; ECONNRESET classified; upstream connection closed and proxy work settled |
| Upstream connection reset | Generic 500 body without upstream exception details |
| Downstream client disconnect | Upstream response connection closed; proxy work settled |

The delayed case has a 38-second request bound and a 40-second test bound. Other
cases have three-second operation bounds and five-second test bounds. Cleanup
destroys any remaining harness sockets even on assertion failure. This is real
HTTP transport coverage, unlike the existing transport-mocked wrapper tests.
The synthetic upstream supplies the sanitized body: Next forwards it rather than
sanitizing arbitrary upstream bodies. Its transport-error response is generic.

Run from `apps/web` on a host permitting loopback listeners:

```sh
node --test tests/proxy-transport.test.cjs
```

This run also passed the 78 offline Python tests, two wrapper tests, full web
ESLint, TypeScript (`npx --no-install tsc --noEmit --incremental false`), and
`git diff --check`. No production application configuration beyond the previously
proposed timeout setting was changed.

### Resource assessment and narrower alternative

The real httpxy implementation uses `ClientRequest.setTimeout` and destroys the
outgoing request on inactivity. Next also destroys upstream requests when the
downstream response closes; the disconnect test verifies that path. Ollama has
its own enforced 300-second total deadline and bounded response size. Existing
proposal rate limiting is per owner (10 requests per five minutes), not a global
concurrency limit. Neither the rate limit nor the provider deadline bounds all
API work, database waits, socket queues, or malicious slow uploads.

The 330-second global rewrite setting increases possible connection retention
for every API rewrite from the prior 30-second inactivity window. It does not
disable cleanup, change provider validation, add retries, or remove existing
limits, but it is not a total wall-clock or concurrency bound. It is acceptable
for controlled development with synthetic or explicitly authorized workloads;
these tests do not justify exposing it to uncontrolled production traffic.

A practical narrower design is an App Router POST handler specifically for
`/api/agents/proposals` (which takes precedence over the fallback rewrite), with
a fixed loopback upstream URL and a 330-second total AbortController deadline.
Other API rewrites could then keep the 30-second default. Such a handler must
forward authentication cookies, idempotency/correlation headers, status and safe
response headers, propagate client cancellation, bound buffered data, and clear
its timer after response consumption. Its CSRF/origin behavior and cancellation
would need dedicated tests. Per-route proxy timeout is not provided by the
current rewrite configuration. This alternative is recommended before broader
deployment, but is not implemented as part of transport verification.

Untested timing behavior: actual 300/330-second boundary expiry, sustained
trickle traffic (which can reset inactivity timeouts), concurrent load and queue
pressure, and full Next router/dev-server integration. The short idle-expiry
test verifies the real timer path without waiting 330 seconds. No Ollama,
PayPal, PostgreSQL, business records, existing services, or migrations were used.

## Sprint 7: bounded structured-output fix

The local `/api/version` endpoint reported Ollama 0.35.1. Read-only `/api/show`
metadata for qwen3:4b advertised both completion and thinking capabilities.
[Ollama's thinking documentation](https://ollama.com/blog/thinking) documents
Qwen 3 support and a top-level boolean `think` parameter on `/api/chat`.
Thinking is generated before final answer content rather than being a separate,
free output channel. The shared generation budget counts those tokens; see the
[runner's NumPredict loop](https://github.com/ollama/ollama/blob/main/mlxrunner/pipeline.go)
and [request budget forwarding](https://github.com/ollama/ollama/blob/main/llm/llama_server.go).
Those source links describe upstream behavior; the local diagnostic establishes
compatibility of the tested request settings on the installed server/model.

Sprint 6's single diagnostic had HTTP 200, elapsed 42.513 seconds, 1,802 response
bytes, completion reason `length`, incomplete output, and OLLAMA_INVALID_RESPONSE.
Exactly one additional generation was authorized and dispatched in Sprint 7.
It used the same dummy, non-purchasing input, schema, adapter parser and grounding
validation, changing only top-level `think` to false and `options.num_predict`
from 300 to 1024. An isolated transport rewrote those two fields before dispatch;
the production adapter was edited only after validation succeeded. A filesystem
guard prevented a second dispatch. Raw input and model/thinking output were
neither printed nor persisted.

| Sanitized diagnostic | Result |
| --- | --- |
| HTTP status | 200 |
| Elapsed time | 9.783 seconds |
| Completion reason | stop |
| Response size | 478 bytes |
| Schema validation | passed |
| Existing adapter parser and grounding validation | passed |
| Error code | none |

The smallest production change is now `think: false` plus `num_predict: 1024`.
Temperature remains zero, context remains 4096, response bytes remain capped at
32,000 and content at 8,000 characters. Diagnostic total deadline was 90 seconds;
production default remains 120 seconds with the existing enforced 1–300 range.
No retries or parser relaxation were added. The larger finite token budget gives
headroom for required JSON fields while disabling unnecessary reasoning. This
single paired-setting comparison does not isolate each setting's contribution,
prove all inputs succeed, or conclusively identify the historical request's cause.

Request regression assertions verify both settings, and truncated-output tests
include incomplete JSON after several valid fields. They still require sanitized
OLLAMA_INVALID_RESPONSE and exactly one mocked POST. Focused offline Python
verification passed: 79 tests. `git diff --check` passed. No frontend files were
changed in Sprint 7, so TypeScript/ESLint were not rerun for this adapter-only fix.

The adapter is ready for controlled end-to-end testing after separately approved
backend activation/reload. The currently running backend remains SIMULATED and
was not restarted or reconfigured. No proposal endpoint, database, payment
operation, migrations, staging, commits, or pushes were used in this sprint.
