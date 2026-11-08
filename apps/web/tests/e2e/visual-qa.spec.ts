import { expect, test } from "@playwright/test";

test("captures mock-only responsive Command Center and AI Assistant", async ({ page }) => {
  test.setTimeout(90_000);
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/contracts") return route.fulfill({ json: { items: [], total: 0, limit: 100, offset: 0 } });
    if (path === "/api/payments/history") return route.fulfill({ json: { items: [] } });
    if (path === "/api/agents/proposals") return route.fulfill({ json: { items: [] } });
    return route.fulfill({ status: 404, json: { detail: "Mock-only visual QA route" } });
  });
  for (const width of [375, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Intelligent spending. Human control." })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: `/tmp/intentra-b2-overview-${width}.png`, fullPage: true, animations: "disabled" });
    await page.goto("/agents");
    await expect(page.getByRole("heading", { name: "AI Purchasing Assistant" })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.getByLabel("Purchase request").focus();
    await expect(page.getByLabel("Purchase request")).toBeFocused();
    await page.screenshot({ path: `/tmp/intentra-b2-assistant-${width}.png`, fullPage: true, animations: "disabled" });
  }
});
