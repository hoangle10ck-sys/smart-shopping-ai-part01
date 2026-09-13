import { defineConfig, devices } from "@playwright/test";
import { existsSync } from "node:fs";

const edgeInstalled = process.platform === "win32" && existsSync("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe");
const python = process.platform === "win32" ? "../backend/.venv/Scripts/python.exe" : "../backend/.venv/bin/python";

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
  use: {
    ...devices["Desktop Chrome"],
    channel: edgeInstalled ? "msedge" : "chromium",
    baseURL: "http://127.0.0.1:13000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    actionTimeout: 10_000,
    serviceWorkers: "block",
  },
  webServer: [
    {
      command: `"${python}" -B -X utf8 ../backend/scripts/run_e2e_backend.py`,
      url: "http://127.0.0.1:18000/api/system/status",
      reuseExistingServer: false,
      timeout: 30_000,
    },
    {
      command: "node e2e/start-frontend.mjs",
      url: "http://127.0.0.1:13000",
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
