import { expect, test } from "@playwright/test";

const contractId = "11111111-1111-4111-8111-111111111111";
const proposalId = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";

test("agent workspace creates, reviews and confirms a simulated plan without payment calls", async ({ page }) => {
  let proposal: Record<string, unknown> | null = null;
  const paymentPosts: string[] = [];
  const proposalIdempotencyKeys: string[] = [];
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === "/api/contracts" && request.method() === "GET") {
      return route.fulfill({ status: 200, json: { items: [{ id: contractId, owner_id: "owner", merchant_id: "office_store", maximum_amount: "100.00", currency: "USD", status: "APPROVED", version: 2, created_at: new Date().toISOString(), approved_at: new Date().toISOString(), approved_by: "owner", revoked_at: null }], total: 1, limit: 100, offset: 0 } });
    }
    if (path === "/api/agents/proposals" && request.method() === "GET") return route.fulfill({ status: 200, json: { items: proposal ? [proposal] : [] } });
    if (path === "/api/agents/proposals" && request.method() === "POST") {
      proposalIdempotencyKeys.push(request.headers()["idempotency-key"] || "");
      proposal = { proposal_id: proposalId, owner_id: "owner", request: request.postDataJSON().request, requested_purpose: "replacement keyboard", merchant_id: "office_store", proposed_amount: "20.00", currency: "USD", contract_id: contractId, contract_version: 2, explanation: "Candidate details extracted.", missing_information: [], policy_decision: "ALLOW", policy_reason: "Within approved contract and current budget.", status: "READY_FOR_REVIEW", provider_mode: "SIMULATED", version: 2, created_at: new Date().toISOString(), updated_at: new Date().toISOString(), payment_preparation: null, events: [] };
      return route.fulfill({ status: 201, json: proposal });
    }
    if (path === `/api/agents/proposals/${proposalId}/confirm` && request.method() === "POST") {
      proposal = { ...proposal!, status: "CONFIRMED", version: 3 };
      return route.fulfill({ status: 200, json: proposal });
    }
    if (path === `/api/agents/proposals/${proposalId}/prepare-payment` && request.method() === "POST") {
      proposal = { ...proposal!, payment_preparation: { reservation_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", attempt_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc", contract_version: 2, created_at: new Date().toISOString(), status: "EXECUTION_PENDING" } };
      return route.fulfill({ status: 200, json: proposal });
    }
    if (path.startsWith("/api/payments/") && request.method() === "POST") paymentPosts.push(path);
    return route.fulfill({ status: 404, json: { detail: "Mock API route not found" } });
  });

  await page.goto("/agents");
  await page.getByLabel("Purchase request").fill("Buy a keyboard for USD 20.00");
  await page.getByLabel("Apply approved contract").selectOption(contractId);
  await page.getByRole("button", { name: "Create proposal" }).click();
  await expect(page.getByText("Simulated AI")).toBeVisible();
  await expect(page.getByText("Allowed by current policy")).toBeVisible();
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Confirm proposal" }).click();
  await expect(page.getByText("Proposal confirmed. Payment has not been reserved or initiated.")).toBeVisible();
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Prepare payment" }).click();
  await expect(page.getByText("Payment prepared", { exact: true })).toBeVisible();
  await expect(page.getByText(/Buyer approval and verified capture are separate/)).toBeVisible();
  await expect(page.getByText("No PayPal order has been created.", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Continue to checkout" })).toBeVisible();
  expect(paymentPosts).toEqual([]);
  expect(proposalIdempotencyKeys).toHaveLength(1);
  expect(proposalIdempotencyKeys[0]).toMatch(/^[0-9a-f-]{36}$/i);
});

test("failed payment preparation stays visible after proposal refresh", async ({ page }) => {
  const prepareRequests: { path: string; method: string }[] = [];
  const proposal = {
    proposal_id: proposalId,
    owner_id: "owner",
    request: "Buy a keyboard for USD 20.00",
    requested_purpose: "replacement keyboard",
    merchant_id: "office_store",
    proposed_amount: "20.00",
    currency: "USD",
    contract_id: contractId,
    contract_version: 2,
    explanation: "Candidate details extracted.",
    missing_information: [],
    policy_decision: "ALLOW",
    policy_reason: "Within approved contract and current budget.",
    status: "CONFIRMED",
    provider_mode: "SIMULATED",
    version: 3,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    payment_preparation: null,
    events: [],
  };

  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === "/api/contracts" && request.method() === "GET") {
      return route.fulfill({ status: 200, json: { items: [], total: 0, limit: 100, offset: 0 } });
    }
    if (path === "/api/agents/proposals" && request.method() === "GET") {
      return route.fulfill({ status: 200, json: { items: [proposal] } });
    }
    if (path === `/api/agents/proposals/${proposalId}/prepare-payment`) {
      prepareRequests.push({ path, method: request.method() });
      return route.fulfill({ status: 409, json: { detail: "Trusted merchant registry is unavailable." } });
    }
    return route.fulfill({ status: 404, json: { detail: "Mock API route not found" } });
  });

  await page.goto("/agents");
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Prepare payment" }).click();

  await expect(page.getByText("Trusted merchant registry is unavailable.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Prepare payment" })).toBeVisible();
  await expect(page.getByText("Payment prepared", { exact: true })).toHaveCount(0);
  expect(prepareRequests).toEqual([{
    path: `/api/agents/proposals/${proposalId}/prepare-payment`,
    method: "POST",
  }]);
});

test("saved proposal detail performs explicit preparation without opening checkout", async ({ page }) => {
  let prepareCalls = 0;
  const proposal = {
    proposal_id: proposalId, owner_id: "owner", request: "Buy a keyboard for USD 20.00",
    requested_purpose: "replacement keyboard", merchant_id: "office_store", proposed_amount: "20.00", currency: "USD",
    contract_id: contractId, contract_version: 2, explanation: "Candidate details extracted.", missing_information: [],
    policy_decision: "ALLOW", policy_reason: "Within approved contract and current budget.", status: "CONFIRMED",
    provider_mode: "SIMULATED", version: 3, created_at: new Date().toISOString(), updated_at: new Date().toISOString(),
    payment_preparation: null, events: [],
  };
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === `/api/agents/proposals/${proposalId}` && route.request().method() === "GET") return route.fulfill({ json: proposal });
    if (path === `/api/agents/proposals/${proposalId}/prepare-payment` && route.request().method() === "POST") {
      prepareCalls += 1;
      return route.fulfill({ json: { ...proposal, payment_preparation: { reservation_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", attempt_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc", contract_version: 2, created_at: new Date().toISOString(), status: "EXECUTION_PENDING" } } });
    }
    return route.fulfill({ status: 404, json: { detail: "Mock API route not found" } });
  });

  await page.goto(`/agents/${proposalId}`);
  await expect(page.getByRole("button", { name: "Prepare payment" })).toBeVisible();
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Prepare payment" }).click();
  await expect(page.getByText("Payment prepared and budget reserved. No PayPal order or buyer approval was created.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Continue to PayPal Sandbox" })).toBeVisible();
  expect(prepareCalls).toBe(1);
});
