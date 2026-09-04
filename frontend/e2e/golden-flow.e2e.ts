/**
 * Flujo dorado operativo sobre el evento demo sembrado (en_ejecucion):
 *
 * 1. El evaluador confirma un estudiante por número ECOE y envía su
 *    evaluación (checklist + modal de confirmación con resumen).
 * 2. El estudiante entra con su cuenta, responde el formulario de su
 *    estación confirmada y lo envía.
 * 3. Coordinación emite un token de kiosco para una estación sin evaluador;
 *    la tablet vinculada muestra automáticamente al estudiante confirmado
 *    y envía su respuesta.
 * 4. Resultados muestra la actividad consolidable.
 *
 * Los pasos de preparación que la UI no expone (check-in de coordinación en
 * otra estación) se hacen por API con la sesión del coordinador.
 */

import { expect, request, test, type APIRequestContext, type Page } from "@playwright/test";

const BASE = process.env.E2E_BASE_URL ?? "http://127.0.0.1:13001";

const ADMIN = { email: "admin@ecoe.cl", password: "e2e-admin-password" };
const EVALUATOR = { email: "eval1@ecoe.cl", password: "e2e-evaluator-password" };
const STUDENT = { email: "student1@ecoe.cl", password: "e2e-student-password" };
const COORDINATOR = { email: "coord@ecoe.cl", password: "e2e-coordinator-password" };

async function login(page: Page, credentials: { email: string; password: string }) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(credentials.email);
  await page.locator('input[type="password"]').fill(credentials.password);
  await page.getByRole("button", { name: "Iniciar sesión" }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/login"));
}

/**
 * Espera a que la página hidrate y termine sus fetch iniciales antes de
 * interactuar: un fill sobre un input aún no hidratado se pierde (React no
 * tiene el onChange conectado y el estado queda vacío).
 */
async function gotoHydrated(page: Page, path: string) {
  await page.goto(path);
  await page.waitForLoadState("networkidle");
}

async function coordinatorApi(): Promise<APIRequestContext> {
  const api = await request.newContext({ baseURL: BASE });
  const response = await api.post("/api/auth/login", { data: COORDINATOR });
  expect(response.ok()).toBeTruthy();
  return api;
}

async function confirmCheckinViaApi(api: APIRequestContext, stationId: number, ecoeNumber: string) {
  const response = await api.post("/api/station-checkins/confirm", {
    data: { ecoe_event_id: 1, station_id: stationId, ecoe_number: ecoeNumber },
  });
  expect(response.ok(), await response.text()).toBeTruthy();
}

test.describe.serial("flujo dorado", () => {
  test("evaluador: check-in + evaluación con modal de resumen", async ({ page }) => {
    await login(page, EVALUATOR);
    await gotoHydrated(page, "/evaluator");

    // E003: sin registros previos (el seed demo ya trae una evaluación de
    // E001 en esta estación, y los duplicados por modo se rechazan).
    await page.getByPlaceholder("Ejemplo: E007").fill("E003");
    await page.getByRole("button", { name: "Confirmar ingreso del estudiante" }).click();
    await expect(page.getByText("Estudiante confirmado", { exact: true })).toBeVisible();
    await expect(page.getByText("E003 · Estudiante3 Demo").first()).toBeVisible();

    // Checklist: marcar todos los criterios como cumplidos.
    const checklistButtons = page.getByRole("button", { name: /Cumplido/ });
    const count = await checklistButtons.count();
    expect(count).toBeGreaterThan(0);
    for (let i = 0; i < count; i += 1) {
      await checklistButtons.nth(i).click();
    }

    await page.getByRole("button", { name: "Guardar evaluación" }).click();
    // Modal propio con resumen (identidad + puntaje) antes del envío final.
    await expect(page.getByRole("dialog")).toContainText("E003 · Estudiante3 Demo");
    await expect(page.getByRole("dialog")).toContainText("20 / 20 pts");
    await page.getByRole("button", { name: "Enviar evaluación" }).click();

    await expect(page.getByText("Evaluación enviada correctamente")).toBeVisible();
  });

  test("estudiante: responde el formulario de su estación confirmada", async ({ page }) => {
    // Coordinación confirma a E001 en la estación 2 (Interpretacion ECG,
    // con formulario del estudiante).
    const api = await coordinatorApi();
    await confirmCheckinViaApi(api, 2, "E001");
    await api.dispose();

    await login(page, STUDENT);
    await gotoHydrated(page, "/student");
    await page.getByPlaceholder("Ejemplo: E007").fill("E001");
    await page.getByRole("button", { name: "Verificar mi ingreso" }).click();
    await expect(page.getByText("Interpretación ECG")).toBeVisible();

    await page.locator("select").last().selectOption("SCA");
    await page.getByRole("button", { name: "Enviar respuesta final" }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Enviar respuesta" }).click();

    await expect(page.getByText("Respuesta enviada correctamente")).toBeVisible();
  });

  test("kiosco: vincular tablet, mostrar estudiante confirmado y responder", async ({ page, browser }) => {
    await login(page, ADMIN);
    await gotoHydrated(page, "/stations");

    // Emitir token de kiosco para la estación sin evaluador (Plan diagnostico).
    const stationRow = page.locator("div.rounded-2xl", { hasText: "Plan diagnóstico" }).first();
    page.once("dialog", (dialog) => dialog.accept());
    await stationRow.getByRole("button", { name: "Modo kiosco" }).click();
    const kioskUrl = (await page.locator("p.font-mono").textContent())?.trim();
    expect(kioskUrl).toBeTruthy();

    // La tablet: contexto propio, sin sesión de usuario.
    const kioskContext = await browser.newContext();
    const kiosk = await kioskContext.newPage();
    await kiosk.goto(kioskUrl!);
    await kiosk.waitForLoadState("networkidle");
    await expect(kiosk.getByText("Esperando al siguiente estudiante")).toBeVisible();

    // Coordinación confirma a E002 en esa estación (id 4).
    const api = await coordinatorApi();
    await confirmCheckinViaApi(api, 4, "E002");
    await api.dispose();

    // El kiosco detecta el check-in por polling y muestra la identidad.
    await expect(kiosk.getByText("E002 · Estudiante2 Demo").first()).toBeVisible({ timeout: 15_000 });

    // OPT-20 F1: una pausa del cronómetro central congela el kiosco (overlay
    // de PAUSA, sin autoenvío); al reanudar, el formulario vuelve.
    const timerApi = await coordinatorApi();
    await timerApi.post("/api/live/control", { data: { ecoe_event_id: 1, action: "start" } });
    await timerApi.post("/api/live/control", { data: { ecoe_event_id: 1, action: "pause" } });
    await expect(
      kiosk.getByText("PAUSA — el cronómetro está detenido"),
    ).toBeVisible({ timeout: 15_000 });
    await timerApi.post("/api/live/control", { data: { ecoe_event_id: 1, action: "resume" } });
    await expect(
      kiosk.getByText("PAUSA — el cronómetro está detenido"),
    ).toHaveCount(0, { timeout: 15_000 });
    await timerApi.dispose();

    await kiosk.getByRole("radio").first().check();
    await kiosk.getByRole("button", { name: "Enviar respuesta final" }).click();
    await kiosk.getByRole("dialog").getByRole("button", { name: "Enviar respuesta" }).click();
    // Tras enviar, el kiosco reemplaza la identidad/respuestas por una pantalla
    // neutra (ver commit "ocultar identidad y respuestas del kiosco tras enviar").
    await expect(kiosk.getByRole("heading", { name: "Respuesta enviada ✓" })).toBeVisible();
    await expect(kiosk.getByText("E002 · Estudiante2 Demo")).toHaveCount(0);

    await kioskContext.close();
  });

  test("resultados: la actividad del flujo aparece consolidable", async ({ page }) => {
    await login(page, ADMIN);
    await gotoHydrated(page, "/results");
    await expect(page.getByText("E001").first()).toBeVisible();
    await expect(page.getByText("E002").first()).toBeVisible();
  });
});
