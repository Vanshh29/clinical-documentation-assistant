import { defineConfig, devices } from '@playwright/test';

// Needs the API, worker, Postgres and Redpanda running. Either `make up` and set
// E2E_BASE_URL=http://localhost:8080 (tests the built containers), or run the apps from source
// and let this start the Vite dev server on :5173.
const baseURL = process.env.E2E_BASE_URL ?? 'http://localhost:5173';
export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: { baseURL, trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : { command: 'npm run dev', url: baseURL, reuseExistingServer: true, timeout: 60_000 },
});
