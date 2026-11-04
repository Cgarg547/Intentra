import http from "node:http";

const attemptId = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const returnState = "e2e-return-state-token-high-entropy-000001";
let returnObserved = false;
let returnCookieObserved = false;
let checkoutFailure = null;
let checkoutCorrelationId = null;

const server = http.createServer(async (request, response) => {
  const chunks = [];
  for await (const chunk of request) chunks.push(chunk);
  const body = Buffer.concat(chunks).toString("utf8");
  const json = (status, value, headers = {}) => {
    response.writeHead(status, { "Content-Type": "application/json", "Cache-Control": "no-store", ...headers });
    response.end(JSON.stringify(value));
  };

  if (request.url === "/health") return json(200, { status: "healthy" });
  if (request.url === "/test/return-observed") return json(200, { observed: returnObserved, cookieObserved: returnCookieObserved });
  if (request.url === "/test/checkout-correlation") return json(200, { correlationId: checkoutCorrelationId });
  if (request.url === "/test/checkout-failure" && request.method === "POST") {
    checkoutFailure = JSON.parse(body);
    return json(200, { configured: true });
  }
  if (request.url === "/test/checkout-failure" && request.method === "DELETE") {
    checkoutFailure = null;
    return json(200, { configured: false });
  }
  if (request.url === `/api/payments/reservations/bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb/checkout` && request.method === "POST") {
    checkoutCorrelationId = request.headers["x-intentra-correlation-id"] ?? null;
    if (checkoutFailure) return json(checkoutFailure.status, { detail: "Internal provider detail must not be forwarded." }, {
      "X-Intentra-Error-Code": checkoutFailure.code,
      "X-Intentra-Correlation-ID": checkoutCorrelationId ?? "",
    });
    return json(201, {
      approval_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
      attempt_id: attemptId,
      provider_order_id: "E2E-ORDER",
      return_state: returnState,
      expires_at: new Date(Date.now() + 30 * 60 * 1000).toISOString(),
      state: "PENDING",
      approval_url: "https://www.sandbox.paypal.com/checkoutnow?token=E2E-ORDER",
    }, { "X-Intentra-Correlation-ID": checkoutCorrelationId ?? "" });
  }
  if (request.url === "/api/payments/checkout/return" && request.method === "POST") {
    const payload = JSON.parse(body);
    returnObserved = payload.state === returnState && payload.attempt_id === attemptId;
    returnCookieObserved = (request.headers.cookie ?? "").includes(`intentra_checkout_state_${attemptId}=${returnState}`);
    return json(200, { approval_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc", attempt_id: attemptId, state: "APPROVED", verified_at: new Date().toISOString() });
  }
  return json(404, { detail: "Mock backend route not found" });
});

server.listen(Number(process.env.MOCK_PORT ?? 8173), "127.0.0.1");
