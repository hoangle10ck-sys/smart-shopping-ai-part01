import { defineConfig, devices } from "@playwright/test";
import { existsSync } from "node:fs";

const edgeInstalled = process.platform === "win32" && existsSync("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe");

export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/*.spec.ts",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: "list",
  outputDir: "test-results",
  globalSetup: "./e2e/global-setup.mjs",
  use: {
    ...devices["Desktop Chrome"],
    channel: edgeInstalled ? "msedge" : "chromium",
    baseURL: "http://127.0.0.1:13000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    actionTimeout: 10_000,
    serviceWorkers: "block",
  },
});
