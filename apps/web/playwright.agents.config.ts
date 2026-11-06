import { defineConfig, devices } from "@playwright/test";

// Uses the already running frontend; never starts/restarts an app or API service.
// Every API request in these specs is intercepted before reaching the proxy.
export default defineConfig({
  testDir: "./tests/e2e",
  testMatch: ["agents.spec.ts", "agent-workspace.spec.ts"],
  fullyParallel: false,
  workers: 1,
  reporter: "list",
  outputDir: "/tmp/intentra-sprint11-playwright",
  use: {
    baseURL: "http://127.0.0.1:3000",
    ...devices["Desktop Chrome"],
    channel: "chrome",
    serviceWorkers: "block",
    trace: "off",
  },
});
