import { defineConfig, devices } from "@playwright/test";

const webPort = process.env.WEB_PORT ?? "3000";

// The specs run against the full Compose stack. make test-all starts it first.
// The spec files run in parallel. The tests in one file run in order.
export default defineConfig({
  testDir: "e2e",
  globalSetup: "./e2e/global-setup.ts",
  outputDir: "../test-results/playwright",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  forbidOnly: Boolean(process.env.CI),
  reporter: [
    ["list"],
    ["html", { outputFolder: "../test-results/playwright-report", open: "never" }],
  ],
  use: {
    baseURL: `http://localhost:${webPort}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
