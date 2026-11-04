import { expect, test, type Page } from "@playwright/test";

const contractId = "11111111-1111-4111-8111-111111111111";
const attemptId = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const reservationId = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";

function sampleContract(status: "DRAFT" | "APPROVED" | "REVOKED" = "APPROVED") {
  return { id: contractId, owner_id: "user-1", merchant_id: "demo-merchant", maximum_amount: "250.00", currency: "USD", status, version: status === "DRAFT" ? 1 : 2, created_at: new Date().toISOString(), approved_at: status === "APPROVED" ? new Date().toISOString() : null, approved_by: status === "APPROVED" ? "user-1" : null, revoked_at: null };
}

async function mockWorkspace(page: Page, options: { attemptState?: string; approvalState?: string | null; historyUnauthorized?: boolean; resumableOrder?: boolean; apiUnauthorized?: boolean; approvalExpired?: boolean } = {}) {
  let contract = sampleContract();
  let attempt: Record<string, unknown> | null = options.attemptState ? {
    attempt_id: attemptId, reservation_id: reservationId, contract_id: contractId,
    provider_order_id: "E2E-ORDER", capture_id: null, attempt_state: options.attemptState,
    reservation_state: "EXECUTION_PENDING", approval_state: options.approvalState ?? null,
    approval_expires_at: options.approvalState === "PENDING" ? new Date(Date.now() + (options.approvalExpired ? -60_000 : 30 * 60_000)).toISOString() : null,
    approval_consumed_at: null,
    merchant_id: "demo-merchant", amount: "24.50", currency: "USD",
    created_at: new Date().toISOString(), updated_at: new Date().toISOString(),
  } : null;
  let approvalReturned = false;
  let captureMode: "COMPLETED" | "FAILED" | "UNKNOWN" = "COMPLETED";

  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    if (path === "/api/auth/me") return route.fulfill({ status: 401, json: { detail: "Not authenticated" } });
    if (options.apiUnauthorized && request.method() === "GET" && ["/api/contracts", "/api/payments/history", "/api/payments/reservations"].includes(path)) return route.fulfill({ status: 401, json: { detail: "Invalid session" } });
    if (path === "/api/contracts" && request.method() === "GET") return route.fulfill({ status: 200, json: { items: [contract], total: 1, limit: 100, offset: 0 } });
    if (path === "/api/contracts" && request.method() === "POST") {
      const input = request.postDataJSON();
      contract = { ...sampleContract("DRAFT"), merchant_id: input.merchant_id, maximum_amount: input.maximum_amount, currency: input.currency };
      return route.fulfill({ status: 201, json: contract });
    }
    if (path === `/api/contracts/${contractId}/approve` && request.method() === "POST") { contract = sampleContract("APPROVED"); return route.fulfill({ status: 200, json: contract }); }
    if (path === `/api/contracts/${contractId}/revoke` && request.method() === "POST") { contract = sampleContract("REVOKED"); return route.fulfill({ status: 200, json: contract }); }
    if (path === "/api/payments/history" && request.method() === "GET") {
      if (options.historyUnauthorized) return route.fulfill({ status: 401, json: { detail: "Session expired" } });
      if (approvalReturned && !attempt) attempt = { attempt_id: attemptId, reservation_id: reservationId, contract_id: contractId, provider_order_id: "E2E-ORDER", capture_id: null, attempt_state: "PENDING", reservation_state: "EXECUTION_PENDING", approval_state: "APPROVED", merchant_id: "demo-merchant", amount: "24.50", currency: "USD", created_at: new Date().toISOString(), updated_at: new Date().toISOString(), approval_verified_at: new Date().toISOString(), events: [] };
      return route.fulfill({ status: 200, json: { items: attempt ? [attempt] : [] } });
    }
    if (path === "/api/payments/reservations" && request.method() === "GET") return route.fulfill({ status: 200, json: { items: options.resumableOrder ? [{ reservation_id: reservationId, contract_id: contractId, merchant_id: "demo-merchant", amount: "24.50", currency: "USD", status: "EXECUTION_PENDING", reason: "Execution pending", created_at: new Date().toISOString() }] : [] } });
    if (path === `/api/payments/attempts/${attemptId}` && request.method() === "GET") {
      if (!attempt) return route.fulfill({ status: 404, json: { detail: "Payment attempt not found" } });
      return route.fulfill({ status: 200, json: attempt });
    }
    if (path === "/api/payments/evaluate" && request.method() === "POST") return route.fulfill({ status: 200, json: { evaluation_id: "evaluation-1", contract_id: contractId, contract_version: 2, decision: "ALLOW", reason: "Payment matches the approved intent contract." } });
    if (path === "/api/payments/reserve" && request.method() === "POST") return route.fulfill({ status: 200, json: { reservation_id: reservationId, contract_id: contractId, contract_version: 2, status: "RESERVED", reason: "Payment budget reserved successfully.", remaining_amount: "225.50" } });
    if (path === `/api/payments/attempts/${attemptId}/capture` && request.method() === "POST") {
      const state = captureMode;
      if (attempt) attempt = { ...attempt, attempt_state: state === "COMPLETED" ? "SUCCEEDED" : state, reservation_state: state === "COMPLETED" ? "CAPTURED" : state === "FAILED" ? "CANCELLED" : "OUTCOME_UNKNOWN", capture_id: state === "COMPLETED" ? "E2E-CAPTURE" : null };
      return route.fulfill({ status: 200, json: { attempt_id: attemptId, state, capture_id: state === "COMPLETED" ? "E2E-CAPTURE" : null, action: state === "COMPLETED" ? "CAPTURE_COMPLETED" : state === "FAILED" ? "CAPTURE_FAILED" : "OUTCOME_UNKNOWN" } });
    }
    if (path === `/api/payments/attempts/${attemptId}/reconcile` && request.method() === "POST") {
      if (attempt) attempt = { ...attempt, attempt_state: "SUCCEEDED", reservation_state: "CAPTURED", capture_id: "E2E-CAPTURE" };
      return route.fulfill({ status: 200, json: { attempt_id: attemptId, action: "CAPTURE_COMPLETED", provider_status: "COMPLETED", capture_id: "E2E-CAPTURE" } });
    }
    return route.fulfill({ status: 404, json: { detail: "Mock API route not found" } });
  });

  await page.route("https://www.sandbox.paypal.com/**", async (route) => {
    const origin = new URL(route.request().headers().referer ?? "http://127.0.0.1:3173").origin;
    const returnUrl = `${origin}/checkout/return?attempt_id=${attemptId}`;
    await route.fulfill({ status: 200, contentType: "text/html", body: `<main><h1>PayPal Sandbox mock</h1><a href="${returnUrl}">Return to INTENTRA</a></main>` });
  });
  await page.route("**/api/auth/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/me")) return route.fulfill({ status: 401, json: { detail: "Not authenticated" } });
    if (path.endsWith("/register") || path.endsWith("/login")) return route.fulfill({ status: 200, headers: { "Set-Cookie": "intentra_session=e2e-session; Path=/; HttpOnly; SameSite=Lax" }, json: { id: "user-1", email: "owner@example.com" } });
    if (path.endsWith("/logout")) return route.fulfill({ status: 204 });
    return route.fulfill({ status: 404, json: { detail: "Not found" } });
  });

  return {
    setApprovedReturn: () => { approvalReturned = true; },
    setCaptureMode: (mode: "COMPLETED" | "FAILED" | "UNKNOWN") => { captureMode = mode; },
  };
}

test("registration, login and logout use the account form", async ({ page }) => {
  await page.route("**/api/auth/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/me")) return route.fulfill({ status: 401, json: { detail: "Not authenticated" } });
    if (path.endsWith("/register") || path.endsWith("/login")) return route.fulfill({ status: 200, headers: { "Set-Cookie": "intentra_session=e2e-session; Path=/; HttpOnly; SameSite=Lax" }, json: { id: "user-1", email: "owner@example.com" } });
    if (path.endsWith("/logout")) return route.fulfill({ status: 204 });
    return route.fulfill({ status: 404 });
  });
  await page.goto("/account");
  await page.getByRole("button", { name: "Create account", exact: true }).first().click();
  await page.getByLabel("Email address").fill("owner@example.com");
  await page.getByLabel("Password").fill("IntentraSecureTestPassword2026!");
  await page.getByRole("button", { name: "Create account", exact: true }).last().click();
  await expect(page.getByText("Signed in as")).toBeVisible();
  await page.getByRole("button", { name: "Sign out" }).click();
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByLabel("Email address").fill("owner@example.com");
  await page.getByLabel("Password").fill("IntentraSecureTestPassword2026!");
  await page.getByRole("button", { name: "Sign in", exact: true }).last().click();
  await expect(page.getByText("Signed in as")).toBeVisible();
});

test("creates a draft contract and approves it", async ({ page }) => {
  await mockWorkspace(page);
  await page.goto("/contracts");
  await page.getByLabel("Merchant ID").fill("demo-merchant");
  await page.getByLabel("Maximum amount").fill("250.00");
  await page.getByLabel("Currency").fill("USD");
  await page.getByRole("button", { name: "Create draft" }).click();
  await expect(page.getByText("Contract details")).toBeVisible();
  await page.getByRole("button", { name: "Approve contract" }).click();
  await expect(page.getByText("APPROVED").first()).toBeVisible();
});

test("evaluates, reserves, redirects through mocked PayPal and verifies return before capture", async ({ page, request }) => {
  const mock = await mockWorkspace(page);
  await page.goto("/payments");
  await page.getByLabel("Approved intent contract").selectOption(contractId);
  await page.getByLabel(/Payment amount/).fill("24.50");
  await page.getByRole("button", { name: "Evaluate payment" }).click();
  await expect(page.getByText("Authorization: ALLOW")).toBeVisible();
  await page.getByRole("button", { name: "Reserve budget" }).click();
  await page.getByRole("button", { name: "Continue to PayPal Sandbox" }).click();
  await expect(page).toHaveURL(/paypal\.com/);
  const stateCookies = await page.context().cookies("http://127.0.0.1:3173/checkout");
  expect(stateCookies.some((cookie) => cookie.name.startsWith("intentra_checkout_state_") && cookie.httpOnly)).toBe(true);
  expect(await page.evaluate(() => document.cookie)).not.toContain("intentra_checkout_state_");
  await page.getByRole("link", { name: "Return to INTENTRA" }).click();
  await expect(page).toHaveURL(/checkout=verified/);
  const callbackEvidence = await request.get("http://127.0.0.1:8173/test/return-observed").then((response) => response.json());
  expect(callbackEvidence).toEqual({ observed: true, cookieObserved: true });
  mock.setApprovedReturn();
  await page.goto("/payments");
  await page.getByRole("button", { name: "Details" }).click();
  await expect(page.locator("dt").filter({ hasText: "Buyer approval" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Capture payment" })).toBeVisible();
  await expect(page.getByText("APPROVED", { exact: true }).first()).toBeVisible();
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Capture payment" }).click();
  await expect(page.getByText(/Capture result: COMPLETED/)).toBeVisible();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: "/tmp/intentra-sprint3-payments.png" });
});

test("uncertain capture outcomes require reconciliation", async ({ page }) => {
  const mock = await mockWorkspace(page, { attemptState: "PENDING", approvalState: "APPROVED" });
  await page.goto("/payments");
  await page.getByRole("button", { name: "Details" }).click();
  mock.setCaptureMode("UNKNOWN");
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Capture payment" }).click();
  await expect(page.getByText(/Capture result: UNKNOWN/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Reconcile provider outcome" })).toBeVisible();
  await page.getByRole("button", { name: "Reconcile provider outcome" }).click();
  await expect(page.getByText(/Reconciliation: CAPTURE_COMPLETED/)).toBeVisible();
});

test("eligible bound order can resume PayPal approval without creating another reservation", async ({ page }) => {
  await mockWorkspace(page, { attemptState: "PENDING", approvalState: "PENDING", resumableOrder: true });
  let handoffCalls = 0;
  await page.route("**/checkout/handoff", async (route) => {
    handoffCalls += 1;
    const body = route.request().postDataJSON() as { reservation_id?: string };
    expect(body.reservation_id).toBe(reservationId);
    return route.fulfill({ status: 200, json: { approval_url: "https://www.sandbox.paypal.com/checkoutnow?token=E2E-ORDER", attempt_id: attemptId } });
  });
  await page.goto("/payments");
  await expect(page.getByRole("button", { name: "Resume PayPal approval" })).toBeVisible();
  await page.getByRole("button", { name: "Resume PayPal approval" }).click();
  await expect(page).toHaveURL(/paypal\.com/);
  expect(handoffCalls).toBe(1);
  await expect(page.getByRole("button", { name: "Capture payment" })).toHaveCount(0);
});

test("checkout proxy preserves sanitized outcome-unknown code and blocks unsafe retry messaging", async ({ page, request }) => {
  await request.post("http://127.0.0.1:8173/test/checkout-failure", {
    data: { status: 503, code: "PROVIDER_OUTCOME_UNKNOWN" },
  });
  await mockWorkspace(page, { attemptState: "PENDING", approvalState: "PENDING", resumableOrder: true });
  await page.goto("/payments");
  const handoffResponse = page.waitForResponse((response) =>
    response.url().endsWith("/checkout/handoff") && response.status() === 503,
  );
  await page.getByRole("button", { name: "Resume PayPal approval" }).click();
  const response = await handoffResponse;
  const correlationId = response.headers()["x-intentra-correlation-id"];
  expect(correlationId).toMatch(/^[0-9a-f-]{36}$/i);
  const propagated = await request.get("http://127.0.0.1:8173/test/checkout-correlation");
  expect((await propagated.json()).correlationId).toBe(correlationId);
  const safeError = page.locator("div[role=alert]").filter({ hasText: "Do not retry" });
  await expect(safeError).toContainText("PayPal may have accepted the order");
  await expect(safeError).not.toContainText("Internal provider detail");
  await request.delete("http://127.0.0.1:8173/test/checkout-failure");
});

test("expired pending approval does not offer resume", async ({ page }) => {
  await mockWorkspace(page, { attemptState: "PENDING", approvalState: "PENDING", approvalExpired: true, resumableOrder: true });
  await page.goto("/payments");
  await expect(page.getByRole("button", { name: "Resume PayPal approval" })).toHaveCount(0);
});

test("definitively failed capture is shown as failed", async ({ page }) => {
  const mock = await mockWorkspace(page, { attemptState: "PENDING", approvalState: "APPROVED" });
  await page.goto("/payments");
  await page.getByRole("button", { name: "Details" }).click();
  mock.setCaptureMode("FAILED");
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Capture payment" }).click();
  await expect(page.getByText(/Capture result: FAILED/)).toBeVisible();
});

test("unauthorized payment history is reported without sample transactions", async ({ page }) => {
  await mockWorkspace(page, { historyUnauthorized: true });
  await page.goto("/payments");
  await expect(page.locator("div[role=alert]").filter({ hasText: "Session expired" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Check sign-in" })).toHaveAttribute("href", "/account");
});

test("API authorization failures are not shown as empty account data", async ({ page }) => {
  await mockWorkspace(page, { apiUnauthorized: true });
  await page.goto("/payments");
  await expect(page.getByRole("alert").filter({ hasText: "session" })).toBeVisible();
  await expect(page.getByText("No approved contracts are available.")).toHaveCount(0);
  await expect(page.getByText("No payment attempts have been created.")).toHaveCount(0);
});

test("payment workspace stays within a mobile viewport", async ({ page }) => {
  await mockWorkspace(page);
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/payments");
  await expect(page.getByRole("heading", { name: "Payments", exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
