/**
 * Recorrido de screenshots para revisión visual. No es un test funcional:
 * se ejecuta a demanda con `npx playwright test screenshots.helper`
 * (requiere el stack e2e arriba y OUT_DIR con permisos de escritura).
 */
import { test } from "@playwright/test";

const BASE = process.env.E2E_BASE_URL ?? "http://127.0.0.1:13001";
const OUT = process.env.SNAP_DIR ?? "/tmp/ecoe-snaps";

const PAGES = [
  "/dashboard",
  "/stations/builder",
  "/stations/builder?stationId=2",
  "/stations/builder?stationId=4",
  "/validation",
  "/stations",
  "/students",
  "/evaluators",
  "/pilotage",
  "/publication",
  "/live",
  "/grading",
  "/results",
  "/instruments",
];

test("captura páginas clave", async ({ page }) => {
  test.skip(!process.env.SNAP_DIR, "Utilitario de revisión visual: correr con SNAP_DIR definido");
  test.setTimeout(180_000);
  await page.goto(`${BASE}/login`);
  await page.getByLabel(/correo/i).fill("admin@ecoe.cl");
  await page.getByLabel(/contraseña/i).fill("e2e-admin-password");
  await page.getByRole("button", { name: "Iniciar sesión" }).click();
  await page.waitForURL(/dashboard/, { timeout: 20_000 });

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.screenshot({ path: `${OUT}/login-post.png` });

  for (const route of PAGES) {
    await page.goto(`${BASE}${route}`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(600);
    const name = route.replace(/\//g, "_");
    await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
  }

  const anon = await page.context().browser()!.newPage();
  await anon.setViewportSize({ width: 1440, height: 900 });
  await anon.goto(`${BASE}/login`);
  await anon.screenshot({ path: `${OUT}/login.png`, fullPage: true });
});
