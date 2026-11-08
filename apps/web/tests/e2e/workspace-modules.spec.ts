import { expect, test, type Page } from "@playwright/test";

const proposalId = "dddddddd-dddd-4ddd-8ddd-dddddddddddd";
const contractId = "11111111-1111-4111-8111-111111111111";

async function mockModules(page: Page) {
  let proposal: Record<string, unknown> = {
    proposal_id: proposalId, owner_id: "owner-1", request: "Buy supplies for USD 12.00",
    requested_purpose: "supplies", merchant_id: "paypal_merchant_demo", proposed_amount: "12.00",
    currency: "USD", contract_id: contractId, contract_version: 2, explanation: "Reviewed request.",
    missing_information: [], policy_decision: "ALLOW", policy_reason: "Within current contract.",
    status: "READY_FOR_REVIEW", provider_mode: "SIMULATED", version: 2,
    created_at: new Date().toISOString(), updated_at: new Date().toISOString(), payment_preparation: null,
    events: [{ event_type: "PROPOSAL_CREATED", actor_id: "owner-1", event_data: {}, created_at: new Date().toISOString() }],
  };
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    if (path === "/api/auth/me") return route.fulfill({ status: 200, json: { id: "owner-1", email: "owner@example.com" } });
    if (path === "/api/agents/proposals" && request.method() === "GET") return route.fulfill({ status: 200, json: { items: [proposal] } });
    if (path === `/api/agents/proposals/${proposalId}/confirm`) {
      proposal = { ...proposal, status: "CONFIRMED", version: 3, events: [...(proposal.events as unknown[]), { event_type: "PROPOSAL_CONFIRMED", actor_id: "owner-1", event_data: {}, created_at: new Date().toISOString() }] };
      return route.fulfill({ status: 200, json: proposal });
    }
    if (path === `/api/agents/proposals/${proposalId}/reject`) {
      const reason = request.postDataJSON().reason;
      proposal = { ...proposal, status: "REJECTED", version: 3, events: [...(proposal.events as unknown[]), { event_type: "PROPOSAL_REJECTED", actor_id: "owner-1", event_data: { reason }, created_at: new Date().toISOString() }] };
      return route.fulfill({ status: 200, json: proposal });
    }
    if (path === "/api/workspace/audit") return route.fulfill({ status: 200, json: { items: [{ event_id: "event-1", correlation_id: "corr-1", entity_type: url.searchParams.get("entity_type") || "payment", entity_id: "attempt-1", related_ids: { contract_id: contractId }, actor_id: "owner-1", actor_email: "owner@example.com", event_type: url.searchParams.get("event_type") || "CAPTURE_COMPLETED", event_data: { amount: "1.00", currency: "USD" }, created_at: new Date().toISOString() }], limit: 50, offset: Number(url.searchParams.get("offset") || 0), next_offset: null } });
    if (path === "/api/workspace/analytics") return route.fulfill({ status: 200, json: {
      payments: { count: 1, successful_count: 1, unknown_count: 0 },
      payment_states: [{ state: "SUCCEEDED", currency: "USD", count: 1, amount: "1.00" }],
      budget_by_contract: [{ contract_id: contractId, merchant_id: "paypal_merchant_demo", maximum_amount: "5.00", currency: "USD", consumed_amount: "1.00", remaining_amount: "4.00", status: "APPROVED" }],
      captured_by_merchant: [{ merchant_id: "paypal_merchant_demo", currency: "USD", amount: "1.00", count: 1 }],
      policy_decisions: { ALLOW: 1, BLOCK: 0, REVIEW: 0 }, proposals: { CONFIRMED: 1 },
      daily_captured: [{ date: "2026-11-01", currency: "USD", amount: "1.00", count: 1 }],
      transactions: [{ attempt_id: "attempt-1", reservation_id: "reserve-1", contract_id: contractId, merchant_id: "paypal_merchant_demo", amount: "1.00", currency: "USD", state: "SUCCEEDED", reservation_state: "CAPTURED", approval_state: "APPROVED", created_at: new Date().toISOString() }],
    } });
    if (path === "/api/workspace/security") return route.fulfill({ status: 200, json: { authenticated: true, active_session_count: 1, current_session_valid: true, contracts: { APPROVED: 1, DRAFT: 0, REVOKED: 0 }, trusted_merchant_count: 1, payment_states: { SUCCEEDED: 1 }, policy_decisions: { ALLOW: 1 }, unresolved_attempts: 0, generated_at: new Date().toISOString() } });
    if (path === "/api/workspace/merchants") return route.fulfill({ status: 200, json: { configured: true, items: [{ internal_merchant_id: "paypal_merchant_demo", paypal_merchant_id: "SANDBOX-MERCHANT-ID", trust_source: "server_configuration", provider_live_verified: false }] } });
    if (path === "/api/workspace/status") return route.fulfill({ status: 200, json: { api: "available", database: "available", paypal_sandbox: "credentials_configured", trusted_merchants: "configured", llm_mode: "simulated", checked_at: new Date().toISOString() } });
    return route.fulfill({ status: 404, json: { detail: "Mock API route not found" } });
  });
}

test("approval center records explicit owner rejection reason", async ({ page }) => {
  await mockModules(page);
  await page.goto("/approvals");
  await expect(page.getByRole("heading", { name: "Approval Center" })).toBeVisible();
  await expect(page.getByText("Simulated extraction")).toBeVisible();
  await page.getByRole("textbox", { name: "Rejection reason" }).fill("No longer needed");
  await page.getByRole("button", { name: "Reject" }).click();
  await expect(page.getByText("Proposal rejected and recorded in its audit history.")).toBeVisible();
  await page.getByRole("button", { name: "Decision history" }).click();
  await page.getByRole("button", { name: /Decision audit history \(\d+\)/ }).click();
  await expect(page.getByText("Reason: No longer needed")).toBeVisible();
});

test("approval confirmation stays separate from payment preparation", async ({ page }) => {
  let paymentRequests = 0;
  await mockModules(page);
  await page.route("**/api/payments/**", async (route) => { paymentRequests += 1; return route.fulfill({ status: 200, json: { items: [] } }); });
  await page.goto("/approvals");
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Confirm proposal" }).click();
  await expect(page.getByText("Proposal confirmed. This did not prepare a payment or approve a PayPal order.")).toBeVisible();
  expect(paymentRequests).toBe(0);
});

test("audit, security, merchant and status screens show live API response data", async ({ page }) => {
  await mockModules(page);
  await page.goto("/audit");
  await expect(page.getByText("CAPTURE_COMPLETED")).toBeVisible();
  await page.getByRole("button", { name: /CAPTURE_COMPLETED/ }).click();
  await page.getByRole("button", { name: "Technical event data" }).click();
  await expect(page.getByText('"amount": "1.00"', { exact: false })).toBeVisible();
  await page.goto("/security");
  await expect(page.getByText("Current session")).toBeVisible();
  await expect(page.getByText("Valid")).toBeVisible();
  await page.goto("/merchants");
  await expect(page.getByText("paypal_merchant_demo").first()).toBeVisible();
  await expect(
    page.getByRole("row", { name: /paypal_merchant_demo/ })
      .getByRole("cell", { name: "Not reverified here" })
  ).toBeVisible();
  await page.goto("/status");
  const health = page.getByRole("region", { name: "System health overview" });
  await expect(health.getByText("Available", { exact: true })).toHaveCount(2);
  await expect(health.getByText("Configured", { exact: true })).toHaveCount(2);
  await expect(page.getByText("AI Simulation Mode")).toBeVisible();
  await expect(page.getByText(/Configured PayPal credentials do not verify PayPal/)).toBeVisible();
});

test("audit filters clear details for an event outside the current results", async ({ page }) => {
  await mockModules(page);
  await page.route("**/api/workspace/audit**", async (route) => {
    const eventType = new URL(route.request().url()).searchParams.get("event_type");
    const first = {
      event_id: "event-first", correlation_id: "corr-first", entity_type: "payment", entity_id: "attempt-first",
      related_ids: {}, actor_id: "owner-1", actor_email: "owner@example.com", event_type: "FIRST_EVENT",
      event_data: { marker: "first" }, created_at: new Date().toISOString(),
    };
    const second = {
      ...first, event_id: "event-second", correlation_id: "corr-second", entity_id: "attempt-second",
      event_type: "SECOND_EVENT", event_data: { marker: "second" },
    };
    await route.fulfill({ status: 200, json: { items: eventType === "SECOND_EVENT" ? [second] : [first], limit: 50, offset: 0, next_offset: null } });
  });

  await page.goto("/audit");
  await page.getByRole("button", { name: "FIRST_EVENT" }).click();
  await page.getByRole("button", { name: "Technical event data" }).click();
  await expect(page.getByText('"marker": "first"', { exact: false })).toBeVisible();
  await page.getByRole("textbox", {
    name: "Event type",
    exact: true,
  }).fill("SECOND_EVENT");
  await expect(page.getByRole("button", { name: "SECOND_EVENT" })).toBeVisible();
  await expect(page.getByText(/Select an event from the timeline to inspect its recorded metadata/)).toBeVisible();
  await expect(page.getByText('"marker": "first"')).toHaveCount(0);
});

test("analytics searches real owner transaction rows and remains mobile sized", async ({ page }) => {
  await mockModules(page);
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/analytics");
  await expect(page.getByText("Successful payments", { exact: true })).toBeVisible();
  await expect(page.locator('[title="attempt-1"]')).toBeVisible();
  await page.getByLabel("Search payment history").fill("not-present");
  await expect(page.getByText("No matching transactions")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
