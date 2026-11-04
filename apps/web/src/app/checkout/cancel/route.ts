import { NextRequest, NextResponse } from "next/server";

const apiBase = () => (process.env.INTENTRA_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

export async function GET(request: NextRequest) {
  const attemptId = request.nextUrl.searchParams.get("attempt_id");
  if (!attemptId || !/^[0-9a-f-]{36}$/i.test(attemptId)) return makeRedirect(request, "cancel-review");
  const stateCookie = `intentra_checkout_state_${attemptId}`;
  const state = request.cookies.get(stateCookie)?.value;
  let result = "cancelled";
  if (state && attemptId) {
    try {
      const response = await fetch(`${apiBase()}/api/payments/checkout/cancel`, {
        method: "POST", cache: "no-store",
        headers: { "Content-Type": "application/json", Cookie: request.headers.get("cookie") ?? "", Origin: request.headers.get("origin") ?? request.nextUrl.origin },
        body: JSON.stringify({ attempt_id: attemptId, state }),
        signal: AbortSignal.timeout(20_000),
      });
      if (!response.ok) result = "cancel-review";
    } catch { result = "cancel-review"; }
  } else {
    result = "cancel-review";
  }
  const redirect = NextResponse.redirect(new URL(`/payments?checkout=${result}`, request.nextUrl.origin), 303);
  redirect.headers.set("Cache-Control", "no-store");
  redirect.headers.set("Referrer-Policy", "no-referrer");
  redirect.cookies.set(stateCookie, "", { httpOnly: true, secure: request.nextUrl.protocol === "https:", sameSite: "lax", path: "/checkout", maxAge: 0 });
  return redirect;
}

function makeRedirect(request: NextRequest, result: string) {
  const response = NextResponse.redirect(new URL(`/payments?checkout=${result}`, request.nextUrl.origin), 303);
  response.headers.set("Cache-Control", "no-store");
  response.headers.set("Referrer-Policy", "no-referrer");
  return response;
}
