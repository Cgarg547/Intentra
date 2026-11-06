import { randomUUID } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";
import { internalApiBase } from "@/lib/server/api-base";

const checkoutMessages: Record<string, string> = {
  AUTHENTICATION_REQUIRED: "Your session is not available. Sign in, then review payment history before continuing.",
  SESSION_INVALID: "Your session has expired. Sign in, then review payment history before continuing.",
  ORIGIN_REJECTED: "The checkout request was blocked by origin security. Reload INTENTRA and review payment history before trying again.",
  CHECKOUT_PROVIDER_UNAVAILABLE: "PayPal Sandbox checkout is not configured or available. This request did not reach order creation; check any earlier checkout before retrying.",
  CHECKOUT_CONFIGURATION_INVALID: "Checkout origin configuration is invalid. No order request was submitted by this request.",
  CHECKOUT_PROVENANCE_MISSING: "This older payment has no verified checkout provenance. Keep it blocked and review provider activity before retrying.",
  PAYMENT_NOT_ELIGIBLE: "This payment is not eligible for checkout. Review its contract and payment state.",
  PROVIDER_NOT_SUBMITTED: "The PayPal order request was not submitted. Review payment history before retrying.",
  PROVIDER_REJECTED: "PayPal explicitly rejected the order request. Review payment history and correct the issue before another attempt.",
  PROVIDER_OUTCOME_UNKNOWN: "PayPal may have accepted the order. Do not retry; review payment history and PayPal Sandbox activity.",
  ORDER_BINDING_RECOVERY_REQUIRED: "PayPal accepted an order but INTENTRA could not finish binding it. Do not retry; use the existing-order recovery process.",
  ORDER_RECOVERY_REQUIRED: "An accepted order needs review before checkout can continue. Do not create another order.",
  CHECKOUT_HANDOFF_INCOMPLETE: "A PayPal order may already exist, but the secure handoff did not finish. Do not retry; review payment history and provider activity.",
  APPROVAL_LINK_INVALID: "INTENTRA could not safely prepare the PayPal redirect. An order may exist; do not retry until it is reviewed.",
  ORDER_LOOKUP_UNAVAILABLE: "INTENTRA could not verify the existing PayPal order. Do not create another order; review payment history.",
  CHECKOUT_STATE_UNCERTAIN: "Checkout could not be confirmed. A PayPal order may exist. Do not retry until payment history and provider activity are reviewed.",
};

function failure(status: number, code: string, message: string, correlationId: string) {
  console.warn(JSON.stringify({
    event: "checkout_handoff_failed",
    error_code: code,
    http_status: status,
    correlation_id: correlationId,
  }));
  return NextResponse.json({ code, detail: message }, {
    status,
    headers: {
      "X-Intentra-Error-Code": code,
      "X-Intentra-Correlation-ID": correlationId,
      "Cache-Control": "no-store",
    },
  });
}

export async function POST(request: NextRequest) {
  const correlationId = randomUUID();
  const input: unknown = await request.json().catch(() => null);
  if (typeof input !== "object" || input === null || !("reservation_id" in input) || typeof input.reservation_id !== "string") {
    return failure(400, "CHECKOUT_REQUEST_INVALID", "Checkout request is invalid.", correlationId);
  }
  const apiBase = internalApiBase();
  if (!apiBase) {
    return failure(503, "CHECKOUT_CONFIGURATION_INVALID", checkoutMessages.CHECKOUT_CONFIGURATION_INVALID, correlationId);
  }
  let providerResponse: Response;
  try {
    providerResponse = await fetch(`${apiBase}/api/payments/reservations/${encodeURIComponent(input.reservation_id)}/checkout`, {
      method: "POST", cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        Cookie: request.headers.get("cookie") ?? "",
        Origin: request.headers.get("origin") ?? request.nextUrl.origin,
        "X-Intentra-Correlation-ID": correlationId,
      },
      body: "{}",
      signal: AbortSignal.timeout(20_000),
    });
  } catch {
    return failure(503, "CHECKOUT_UPSTREAM_UNCERTAIN", "INTENTRA could not confirm whether the checkout request reached the API. A PayPal order may exist. Do not retry; review payment history and provider activity.", correlationId);
  }
  const payload: unknown = await providerResponse.json().catch(() => null);
  if (!providerResponse.ok) {
    const code = providerResponse.headers.get("X-Intentra-Error-Code") ?? "CHECKOUT_REQUEST_REJECTED";
    const message = checkoutMessages[code]
      ?? "Checkout was rejected. Review payment history and provider activity before taking another action.";
    return failure(providerResponse.status, code, message, correlationId);
  }
  if (typeof payload !== "object" || payload === null || !("return_state" in payload) || typeof payload.return_state !== "string" || payload.return_state.length < 32 || !("attempt_id" in payload) || typeof payload.attempt_id !== "string" || !("approval_url" in payload) || typeof payload.approval_url !== "string" || !("expires_at" in payload) || typeof payload.expires_at !== "string" || !Number.isFinite(Date.parse(payload.expires_at)) || Date.parse(payload.expires_at) <= Date.now()) {
    return failure(502, "CHECKOUT_RESPONSE_INVALID", "INTENTRA could not safely prepare the PayPal redirect. An order may exist; do not retry until it is reviewed.", correlationId);
  }
  let approval: URL;
  try { approval = new URL(payload.approval_url); } catch { return failure(502, "APPROVAL_LINK_INVALID", checkoutMessages.APPROVAL_LINK_INVALID, correlationId); }
  if (approval.protocol !== "https:" || approval.hostname !== "www.sandbox.paypal.com") {
    return failure(502, "APPROVAL_LINK_INVALID", checkoutMessages.APPROVAL_LINK_INVALID, correlationId);
  }
  const maxAge = Math.max(0, Math.min(7200, Math.floor((Date.parse(payload.expires_at) - Date.now()) / 1000)));
  const response = NextResponse.json({ approval_url: approval.toString(), attempt_id: payload.attempt_id });
  const cookieOptions = { httpOnly: true, secure: request.nextUrl.protocol === "https:", sameSite: "lax" as const, path: "/checkout", maxAge };
  const stateCookie = `intentra_checkout_state_${payload.attempt_id}`;
  response.cookies.set(stateCookie, payload.return_state, cookieOptions);
  response.headers.set("Cache-Control", "no-store");
  response.headers.set("Referrer-Policy", "no-referrer");
  response.headers.set("X-Intentra-Correlation-ID", correlationId);
  return response;
}
