import { defineConfig } from "@playwright/test";

/**
 * E2E del flujo dorado contra el stack efímero de docker-compose.e2e.yml
 * (ver scripts/run_e2e.sh). Nunca apuntar estas pruebas a producción: crean
 * check-ins, evaluaciones y respuestas reales sobre el evento demo.
 */
export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/*.e2e.ts",
  timeout: 60_000,
  expect: { timeout: 12_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://127.0.0.1:13001",
    trace: "retain-on-failure",
  },
});
