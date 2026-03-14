const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "/backend/api";

async function request<T>(
  path: string,
  options: RequestInit = {},
  token?: string | null,
): Promise<T> {
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
    cache: "no-store",
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || "No se pudo completar la solicitud");
  }

  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    return response.json() as Promise<T>;
  }

  return response.blob() as T;
}

export const api = {
  login: (email: string, password: string) =>
    request<{ access_token: string; user: Record<string, unknown> }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  me: (token: string) => request("/auth/me", {}, token),
  listECOE: (token: string) => request("/ecoe", {}, token),
  dashboard: (eventId: number, token: string) => request(`/dashboard/${eventId}`, {}, token),
  validation: (eventId: number, token: string) => request(`/validation/${eventId}`, {}, token),
  students: (eventId: number, token: string) => request(`/students/${eventId}`, {}, token),
  createStudent: (payload: unknown, token: string) =>
    request("/students", { method: "POST", body: JSON.stringify(payload) }, token),
  importStudents: (eventId: number, file: File, token: string) => {
    const formData = new FormData();
    formData.append("file", file);
    return request(`/students/import?ecoe_event_id=${eventId}`, { method: "POST", body: formData }, token);
  },
  staff: (eventId: number, token: string) => request(`/staff/${eventId}`, {}, token),
  createStaff: (payload: unknown, token: string) =>
    request("/staff", { method: "POST", body: JSON.stringify(payload) }, token),
  importStaff: (eventId: number, file: File, token: string) => {
    const formData = new FormData();
    formData.append("file", file);
    return request(`/staff/import?ecoe_event_id=${eventId}`, { method: "POST", body: formData }, token);
  },
  stations: (eventId: number, token: string) => request(`/stations/${eventId}`, {}, token),
  createStation: (payload: unknown, token: string) =>
    request("/stations", { method: "POST", body: JSON.stringify(payload) }, token),
  updateStation: (stationId: number, payload: unknown, token: string) =>
    request(`/stations/${stationId}`, { method: "PUT", body: JSON.stringify(payload) }, token),
  templates: (token: string) => request("/templates", {}, token),
  createTemplate: (payload: unknown, token: string) =>
    request("/templates", { method: "POST", body: JSON.stringify(payload) }, token),
  instruments: (token: string) => request("/instruments", {}, token),
  createInstrument: (payload: unknown, token: string) =>
    request("/instruments", { method: "POST", body: JSON.stringify(payload) }, token),
  simulatedPatients: (token: string) => request("/simulated-patients", {}, token),
  createSimulatedPatient: (payload: unknown, token: string) =>
    request("/simulated-patients", { method: "POST", body: JSON.stringify(payload) }, token),
  pilotage: (eventId: number, token: string) => request(`/pilotage/${eventId}`, {}, token),
  createPilotage: (payload: unknown, token: string) =>
    request("/pilotage", { method: "POST", body: JSON.stringify(payload) }, token),
  archivePilotage: (id: number, token: string) =>
    request(`/pilotage/${id}/archive`, { method: "POST" }, token),
  live: (eventId: number, token: string) => request(`/live/${eventId}`, {}, token),
  liveControl: (payload: unknown, token: string) =>
    request("/live/control", { method: "POST", body: JSON.stringify(payload) }, token),
  submitEvaluator: (payload: unknown, token: string) =>
    request("/evaluator/submit", { method: "POST", body: JSON.stringify(payload) }, token),
  submitStudent: (payload: unknown, token: string) =>
    request("/student/submit", { method: "POST", body: JSON.stringify(payload) }, token),
  results: (eventId: number, token: string) => request(`/results/${eventId}`, {}, token),
  incidents: (eventId: number, token: string) => request(`/incidents/${eventId}`, {}, token),
};
