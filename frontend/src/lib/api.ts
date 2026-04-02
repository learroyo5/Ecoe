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
  ecoe: (eventId: number, token: string) => request(`/ecoe/${eventId}`, {}, token),
  updateECOE: (eventId: number, payload: unknown, token: string) =>
    request(`/ecoe/${eventId}`, { method: "PUT", body: JSON.stringify(payload) }, token),
  dashboard: (eventId: number, token: string) => request(`/dashboard/${eventId}`, {}, token),
  updateECOETiming: (eventId: number, payload: unknown, token: string) =>
    request(`/ecoe/${eventId}/timing`, { method: "PATCH", body: JSON.stringify(payload) }, token),
  validation: (eventId: number, token: string) => request(`/validation/${eventId}`, {}, token),
  students: (eventId: number, token: string) => request(`/students/${eventId}`, {}, token),
  createStudent: (payload: unknown, token: string) =>
    request("/students", { method: "POST", body: JSON.stringify(payload) }, token),
  updateStudentStatus: (studentId: number, payload: unknown, token: string) =>
    request(`/students/${studentId}/status`, { method: "PATCH", body: JSON.stringify(payload) }, token),
  deleteStudent: (studentId: number, token: string) =>
    request(`/students/${studentId}`, { method: "DELETE" }, token),
  deduplicateStudentsByRut: (eventId: number, token: string) =>
    request(`/students/${eventId}/deduplicate-rut`, { method: "POST" }, token),
  renumberStudents: (eventId: number, token: string) =>
    request(`/students/${eventId}/renumber`, { method: "POST" }, token),
  importStudents: (eventId: number, file: File, token: string) => {
    const formData = new FormData();
    formData.append("file", file);
    return request(`/students/import?ecoe_event_id=${eventId}`, { method: "POST", body: formData }, token);
  },
  staff: (eventId: number, token: string) => request(`/staff/${eventId}`, {}, token),
  createStaff: (payload: unknown, token: string) =>
    request("/staff", { method: "POST", body: JSON.stringify(payload) }, token),
  updateStaff: (staffId: number, payload: unknown, token: string) =>
    request(`/staff/${staffId}`, { method: "PATCH", body: JSON.stringify(payload) }, token),
  deleteStaff: (staffId: number, token: string) =>
    request(`/staff/${staffId}`, { method: "DELETE" }, token),
  deduplicateStaffByEmail: (eventId: number, token: string) =>
    request(`/staff/${eventId}/deduplicate-email`, { method: "POST" }, token),
  importStaff: (eventId: number, file: File, token: string) => {
    const formData = new FormData();
    formData.append("file", file);
    return request(`/staff/import?ecoe_event_id=${eventId}`, { method: "POST", body: formData }, token);
  },
  evaluatorContext: (eventId: number, token: string) => request(`/evaluator/context/${eventId}`, {}, token),
  confirmStationCheckin: (payload: unknown, token: string) =>
    request("/station-checkins/confirm", { method: "POST", body: JSON.stringify(payload) }, token),
  studentAccess: (payload: unknown, token: string) =>
    request("/student/access", { method: "POST", body: JSON.stringify(payload) }, token),
  stationBank: (token: string) => request("/station-bank", {}, token),
  createStationBank: (payload: unknown, token: string) =>
    request("/station-bank", { method: "POST", body: JSON.stringify(payload) }, token),
  updateStationBank: (bankStationId: number, payload: unknown, token: string) =>
    request(`/station-bank/${bankStationId}`, { method: "PUT", body: JSON.stringify(payload) }, token),
  updateStationBankStatus: (bankStationId: number, payload: unknown, token: string) =>
    request(`/station-bank/${bankStationId}/status`, { method: "PATCH", body: JSON.stringify(payload) }, token),
  stations: (eventId: number, token: string) => request(`/stations/${eventId}`, {}, token),
  createStation: (payload: unknown, token: string) =>
    request("/stations", { method: "POST", body: JSON.stringify(payload) }, token),
  updateStation: (stationId: number, payload: unknown, token: string) =>
    request(`/stations/${stationId}`, { method: "PUT", body: JSON.stringify(payload) }, token),
  media: (stationId: number, token: string) => request(`/media/${stationId}`, {}, token),
  deleteMedia: (assetId: number, token: string) =>
    request(`/media/${assetId}`, { method: "DELETE" }, token),
  mediaFile: (assetId: number, token: string) => request<Blob>(`/media/file/${assetId}`, {}, token),
  uploadMedia: (
    payload: { ecoe_event_id: number; station_id?: number | null; target_viewer?: string; file: File },
    token: string,
  ) => {
    const formData = new FormData();
    formData.append("file", payload.file);
    const stationId = payload.station_id ? `&station_id=${payload.station_id}` : "";
    const targetViewer = payload.target_viewer ?? "estudiante";
    return request(
      `/media/upload?ecoe_event_id=${payload.ecoe_event_id}${stationId}&target_viewer=${targetViewer}`,
      { method: "POST", body: formData },
      token,
    );
  },
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
