import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  reporter: "list",
  use: { baseURL: "http://127.0.0.1:3173", trace: "retain-on-failure", screenshot: "only-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    { command: "node tests/e2e/mock-api.mjs", url: "http://127.0.0.1:8173/health", reuseExistingServer: false, timeout: 30_000, env: { MOCK_PORT: "8173" } },
    { command: "npm run dev -- --hostname 127.0.0.1 --port 3173", url: "http://127.0.0.1:3173", reuseExistingServer: false, timeout: 120_000, env: { INTENTRA_API_URL: "http://127.0.0.1:8173", INTENTRA_NEXT_DIST_DIR: ".next-e2e" } },
  ],
});
