import { expect, test, type Page } from "@playwright/test";

async function mockReadOnlyApi(page: Page) {
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/auth/me") return route.fulfill({ json: { id: "qa-owner", email: "qa-owner@example.com" } });
    if (path === "/api/contracts") return route.fulfill({ json: { items: [], total: 0, limit: 100, offset: 0 } });
    if (path === "/api/agents/proposals") return route.fulfill({ json: { items: [] } });
    if (path === "/api/payments/history" || path === "/api/payments/reservations") return route.fulfill({ json: { items: [] } });
    if (path === "/api/workspace/audit") return route.fulfill({ json: { items: [], limit: 50, offset: 0, next_offset: null } });
    if (path === "/api/workspace/security") return route.fulfill({ json: { authenticated: true, active_session_count: 0, current_session_valid: false, contracts: {}, trusted_merchant_count: 0, payment_states: {}, policy_decisions: {}, unresolved_attempts: 0, generated_at: new Date().toISOString() } });
    if (path === "/api/workspace/analytics") return route.fulfill({ json: { payments: { count: 0, successful_count: 0, unknown_count: 0 }, payment_states: [], budget_by_contract: [], captured_by_merchant: [], policy_decisions: {}, proposals: {}, daily_captured: [], transactions: [] } });
    if (path === "/api/workspace/merchants") return route.fulfill({ json: { configured: false, items: [] } });
    if (path === "/api/workspace/status") return route.fulfill({ json: { api: "available", database: "available", paypal_sandbox: "unconfigured", trusted_merchants: "unconfigured", llm_mode: "simulated", checked_at: new Date().toISOString() } });
    return route.fulfill({ status: 404, json: { detail: "Mock-only QA route" } });
  });
}

function collectBrowserErrors(page: Page) {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(`pageerror: ${error.message}`));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(`console: ${message.text()}`);
  });
  return errors;
}

test("mobile drawer supports focus, Escape, overlay dismissal, and accessible navigation", async ({ page }) => {
  await mockReadOnlyApi(page);
  const browserErrors = collectBrowserErrors(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");

  const skipLink = page.getByRole("link", { name: "Skip to main content" });
  await skipLink.focus();
  await expect(skipLink).toBeFocused();

  const drawer = page.getByLabel("Primary navigation");
  const open = page.getByRole("button", { name: "Open navigation" });
  await open.focus();
  await expect(open).toBeFocused();
  await open.press("Enter");
  await expect(drawer).toHaveClass(/translate-x-0/);
  await expect(page.getByRole("button", { name: "Close navigation overlay" })).toBeVisible();

  await page.keyboard.press("Escape");
  await expect(drawer).toHaveClass(/-translate-x-full/);
  await open.click();
  await page.getByRole("button", { name: "Close navigation overlay" }).click();
  await expect(drawer).toHaveClass(/-translate-x-full/);
  expect(browserErrors).toEqual([]);
});

test("desktop and mobile sidebar links navigate without browser errors", async ({ page }) => {
  await mockReadOnlyApi(page);
  const browserErrors = collectBrowserErrors(page);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/");
  await page.getByLabel("Primary navigation").getByRole("link", { name: "Intent Contracts" }).click();
  await expect(page).toHaveURL(/\/contracts$/);
  await expect(page.getByRole("heading", { name: "Intent Contracts" })).toBeVisible();

  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page.getByLabel("Primary navigation").getByRole("link", { name: "AI Agents" }).click();
  await expect(page).toHaveURL(/\/agents$/);
  await expect(page.getByRole("heading", { name: "AI Purchasing Assistant" })).toBeVisible();
  expect(browserErrors).toEqual([]);
});

test("workspace modules remain horizontally contained on mobile", async ({ page }) => {
  await mockReadOnlyApi(page);
  const browserErrors = collectBrowserErrors(page);
  await page.setViewportSize({ width: 390, height: 844 });
  for (const path of ["/", "/contracts", "/agents", "/payments", "/approvals", "/analytics", "/security", "/audit", "/merchants", "/status", "/settings", "/account"]) {
    await page.goto(path);
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  }
  expect(browserErrors).toEqual([]);
});
