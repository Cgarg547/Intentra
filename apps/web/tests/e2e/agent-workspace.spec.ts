import { expect, test as base, type Page, type Route } from "@playwright/test";
import type { AgentProposal } from "../../src/lib/agents/client";

const proposalId = "dddddddd-dddd-4ddd-8ddd-dddddddddddd";
const prompt = "Synthetic readiness diagnostic. No purchase is requested.";
function saved(overrides: Partial<AgentProposal> = {}): AgentProposal {
  return {
    proposal_id: proposalId, owner_id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee", request: prompt,
    requested_purpose: null, merchant_id: null, proposed_amount: null, currency: null,
    contract_id: null, contract_version: null, explanation: "Extracted details require review.",
    missing_information: ["amount", "currency", "approved contract"],
    policy_decision: "NEEDS_INFORMATION", policy_reason: "Select an approved contract and provide purchase details.",
    status: "NEEDS_INFORMATION", provider_mode: "OLLAMA", version: 2,
    created_at: "2026-11-05T02:36:33.000Z", updated_at: "2026-11-05T02:36:42.000Z",
    payment_preparation: null, events: [], ...overrides,
  };
}

type Api = {
  history: AgentProposal[];
  historyStatus: number;
  mode: "success" | "hold" | "network" | "unauthorized" | "session_invalid" | "validation" | "unavailable" | "malformed";
  posts: { key: string; body: { request: string; contract_id: string | null } }[];
  reads: string[];
  pending: Route[];
};
const test = base.extend<{ api: Api }>({
  api: [async ({ page }, use, testInfo) => {
    const api: Api = { history: [], historyStatus: 200, mode: "success", posts: [], reads: [], pending: [] };
    const unexpectedWrites: string[] = [];
    // Block external hosts and fulfill ALL /api paths, including unknown mutations.
    // No live backend, Ollama, PayPal, cookie, or user data is involved.
    const appOrigin = new URL(testInfo.project.use.baseURL ?? "http://127.0.0.1").origin;
    await page.route("**/*", async (route) => {
      const request = route.request();
      const url = new URL(request.url());
      if (url.origin !== appOrigin) return route.abort();
      if (!url.pathname.startsWith("/api/")) return route.continue();
      const path = url.pathname;
      if (request.method() === "GET") {
        api.reads.push(path);
        if (path === "/api/contracts") return route.fulfill({ json: { items: [], total: 0, limit: 100, offset: 0 } });
        if (path === "/api/agents/proposals") return route.fulfill({ status: api.historyStatus, json: api.historyStatus === 200 ? { items: api.history } : { detail: "Not authenticated" } });
        if (path === `/api/agents/proposals/${proposalId}`) return route.fulfill({ json: saved() });
        return route.fulfill({ status: 404, json: { detail: "Synthetic route unavailable" } });
      }
      if (request.method() === "POST" && path === "/api/agents/proposals") {
        api.posts.push({ key: request.headers()["idempotency-key"], body: request.postDataJSON() });
        if (api.mode === "hold") { api.pending.push(route); return; }
        if (api.mode === "network") return route.abort("failed");
        if (api.mode === "unauthorized") return route.fulfill({ status: 401, json: { detail: "Not authenticated" } });
        if (api.mode === "session_invalid") return route.fulfill({ status: 401, headers: { "X-Intentra-Error-Code": "SESSION_INVALID" }, json: { detail: "Invalid session" } });
        if (api.mode === "validation") return route.fulfill({ status: 422, json: { detail: [] } });
        if (api.mode === "unavailable") return route.fulfill({ status: 503, json: { detail: "Provider unavailable" } });
        if (api.mode === "malformed") return route.fulfill({ status: 201, json: { id: proposalId } });
        const result = saved({ request: api.posts.at(-1)!.body.request });
        api.history = [result];
        return route.fulfill({ status: 201, json: result });
      }
      unexpectedWrites.push(`${request.method()} ${path}`);
      return route.fulfill({ status: 403, json: { detail: "Mutation prohibited in this test" } });
    });
    await use(api);
    for (const route of api.pending) await route.abort().catch(() => {});
    expect(unexpectedWrites, "creation must not confirm, prepare, pay, or mutate contracts").toEqual([]);
  }, { auto: true }],
});

async function open(page: Page) {
  await page.goto("/agents");
  await expect(page.getByRole("button", { name: "Create proposal", exact: true })).toBeEnabled();
  await page.getByLabel("Purchase request", { exact: true }).fill(prompt);
}

test("201 maps proposal_id, renders OLLAMA NEEDS_INFORMATION, and permits no contract", async ({ page, api }) => {
  await open(page);
  await expect(page.getByText("No proposals yet.", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Create proposal", exact: true }).click();
  const card = page.getByRole("article", { name: `Proposal ${proposalId}`, exact: true });
  await expect(card.locator("dd").filter({ hasText: proposalId })).toBeVisible();
  await expect(card.getByText("OLLAMA", { exact: true })).toBeVisible();
  await expect(card.getByText("Needs information", { exact: true })).toHaveCount(2);
  await expect(card.getByText("Select an approved contract and provide purchase details.", { exact: true })).toBeVisible();
  await expect(card.getByRole("list", { name: "Missing information" })).toContainText("approved contract");
  await expect(card.getByRole("link", { name: /View saved proposal/ })).toHaveAttribute("href", `/agents/${proposalId}`);
  const result = page.getByRole("region", { name: "New proposal result" });
  await expect(result.getByRole("heading", { name: "More information is needed" })).toBeVisible();
  await expect(result).toContainText("Creating it did not reserve funds or initiate payment.");
  await expect(result.getByRole("link", { name: "Review saved proposal" })).toHaveAttribute("href", `/agents/${proposalId}`);
  await expect(page.getByText("Payment prepared", { exact: true })).toHaveCount(0);
  expect(api.posts).toHaveLength(1);
  expect(api.posts[0].body).toEqual({ request: prompt, contract_id: null });
  expect(api.posts[0].key).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i);
});

test("each deliberate submission gets a fresh key, including identical text", async ({ page, api }) => {
  await open(page);
  await page.getByRole("button", { name: "Create proposal", exact: true }).click();
  await expect(page.getByRole("article")).toHaveCount(1);
  await page.getByLabel("Purchase request", { exact: true }).fill(prompt);
  await page.getByRole("button", { name: "Create proposal", exact: true }).click();
  await expect.poll(() => api.posts.length).toBe(2);
  expect(new Set(api.posts.map((post) => post.key)).size).toBe(2);
});

test("synchronous duplicate submits send only one POST", async ({ page, api }) => {
  api.mode = "hold";
  await open(page);
  await page.locator("form").evaluate((form) => {
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
  });
  await expect.poll(() => api.posts.length).toBe(1);
  await expect(page.getByRole("button", { name: "Creating proposal…" })).toBeDisabled();
  await page.getByRole("button", { name: "Stop waiting" }).click();
  await expect(page.getByRole("region", { name: "Interrupted request" })).toBeVisible();
  expect(api.posts).toHaveLength(1);
});

test("stop waiting preserves uncertainty and requires history review before a new request", async ({ page, api }) => {
  api.mode = "hold";
  await open(page);
  await page.getByRole("button", { name: "Create proposal", exact: true }).click();
  await expect.poll(() => api.posts.length).toBe(1);
  const key = api.posts[0].key;
  await page.getByRole("button", { name: "Stop waiting" }).click();
  await expect(page.getByText("You stopped waiting. The server may still finish this request.", { exact: true })).toBeVisible();
  await expect(page.getByText(`Submission reference: ${key}`, { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Create proposal", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: /I reviewed history/ })).toBeDisabled();
  api.history = [saved()];
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  await expect(page.getByRole("article")).toHaveCount(1);
  await expect(page.getByRole("button", { name: /I reviewed history/ })).toBeEnabled();
  expect(api.posts).toHaveLength(1);
});

test("finite timeout never retries and reports an uncertain server outcome", async ({ page, api }) => {
  api.mode = "hold";
  await page.clock.install();
  await open(page);
  await page.getByRole("button", { name: "Create proposal", exact: true }).click();
  await expect.poll(() => api.posts.length).toBe(1);
  await page.clock.runFor(340_100);
  await expect(page.getByText("The waiting limit was reached. The request was not retried.", { exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "Interrupted request" })).toContainText("may still have created a proposal");
  await page.clock.runFor(60_000);
  expect(api.posts).toHaveLength(1);
});

for (const mode of ["network", "unavailable", "malformed"] as const) {
  test(`${mode} response does not retry or falsely show success`, async ({ page, api }) => {
    api.mode = mode;
    await open(page);
    await page.getByRole("button", { name: "Create proposal", exact: true }).click();
    await expect(page.getByRole("region", { name: "Interrupted request" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Create proposal", exact: true })).toBeDisabled();
    await expect(page.getByRole("article")).toHaveCount(0);
    expect(api.posts).toHaveLength(1);
  });
}

test("bare unauthorized submission reports an unavailable or protected API and does not retry", async ({ page, api }) => {
  api.mode = "unauthorized";
  await open(page);
  await page.getByRole("button", { name: "Create proposal", exact: true }).click();
  await expect(page.locator("#main-content").getByRole("alert")).toContainText("API is unavailable or protected");
  await expect(page.getByRole("button", { name: "Create proposal", exact: true })).toBeDisabled();
  await expect(page.getByRole("link", { name: "Sign in", exact: true })).toBeVisible();
  expect(api.posts).toHaveLength(1);
});

test("coded invalid session reports expiry and does not retry", async ({ page, api }) => {
  api.mode = "session_invalid";
  await open(page);
  await page.getByRole("button", { name: "Create proposal", exact: true }).click();
  await expect(page.locator("#main-content").getByRole("alert")).toContainText("Your session has expired");
  await expect(page.getByRole("button", { name: "Create proposal", exact: true })).toBeDisabled();
  expect(api.posts).toHaveLength(1);
});

test("unauthenticated history gates submission without creating an account or proposal", async ({ page, api }) => {
  api.historyStatus = 401;
  await page.goto("/agents");
  await expect(page.getByRole("link", { name: "Sign in to your account" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Create proposal", exact: true })).toBeDisabled();
  expect(api.posts).toHaveLength(0);
});

test("a session change clears saved data and stops waiting without resubmitting", async ({ page, api }) => {
  api.mode = "hold";
  api.history = [saved()];
  await open(page);
  await expect(page.getByRole("article")).toHaveCount(1);
  await page.getByRole("button", { name: "Create proposal", exact: true }).click();
  await expect.poll(() => api.posts.length).toBe(1);
  api.historyStatus = 401;
  await page.evaluate(() => window.dispatchEvent(new Event("intentra:auth-changed")));
  await expect(page.getByRole("article")).toHaveCount(0);
  await expect(page.locator("#main-content").getByRole("alert").filter({ hasText: "Your session changed while waiting" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Create proposal", exact: true })).toBeDisabled();
  expect(api.posts).toHaveLength(1);
});

test("validation errors are friendly and blank requests never POST", async ({ page, api }) => {
  api.mode = "validation";
  await open(page);
  await page.getByLabel("Purchase request", { exact: true }).fill("   ");
  await page.getByRole("button", { name: "Create proposal", exact: true }).click();
  await expect(page.locator("#main-content").getByRole("alert")).toContainText("between 1 and 4,000 characters");
  expect(api.posts).toHaveLength(0);
  await expect(page.getByLabel("Purchase request", { exact: true })).toHaveAttribute("maxlength", "4000");
  await page.getByLabel("Purchase request", { exact: true }).fill(prompt);
  await page.getByRole("button", { name: "Create proposal", exact: true }).click();
  await expect(page.locator("#main-content").getByRole("alert")).toContainText("Check your request and contract selection");
  expect(api.posts).toHaveLength(1);
});

test("history shows real states, draft is not labeled evaluated, refresh is read only", async ({ page, api }) => {
  api.history = [saved({ status: "DRAFT", policy_decision: null, policy_reason: null }), saved({ proposal_id: "ffffffff-ffff-4fff-8fff-ffffffffffff", status: "REJECTED", provider_mode: "SIMULATED" })];
  await page.goto("/agents");
  await expect(page.getByRole("article")).toHaveCount(2);
  await expect(page.getByText("Not evaluated", { exact: true })).toBeVisible();
  await expect(page.getByText("Rejected", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  await expect(page.getByRole("button", { name: "Refresh", exact: true })).toBeEnabled();
  expect(api.posts).toHaveLength(0);
});

test("saved detail route loads proposal_id through GET only", async ({ page, api }) => {
  await page.goto(`/agents/${proposalId}`);
  await expect(page.getByRole("heading", { name: "Proposal details" })).toBeVisible();
  await expect(page.getByText(proposalId, { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Confirm proposal" })).toHaveCount(0);
  // Development Strict Mode may repeat the initial read effect; refresh adds one GET.
  const initialReads = api.reads.filter((path) => path === `/api/agents/proposals/${proposalId}`).length;
  await page.getByRole("button", { name: "Refresh proposal" }).click();
  await expect(page.getByRole("button", { name: "Refresh proposal" })).toBeEnabled();
  expect(api.reads.filter((path) => path === `/api/agents/proposals/${proposalId}`)).toHaveLength(initialReads + 1);
  expect(api.posts).toHaveLength(0);
});

test("mobile workspace fits the viewport and exposes accessible controls", async ({ page, api }) => {
  api.history = [saved()];
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/agents");
  await expect(page.getByRole("heading", { name: "AI Purchasing Assistant", exact: true })).toBeVisible();
  await expect(page.getByRole("article")).toHaveCount(1);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.getByLabel("Purchase request", { exact: true }).focus();
  await expect(page.getByLabel("Purchase request", { exact: true })).toBeFocused();
  await page.screenshot({ path: "/tmp/intentra-sprint11-mobile.png", fullPage: true, animations: "disabled" });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({ path: "/tmp/intentra-sprint11-desktop.png", fullPage: true, animations: "disabled" });
});
