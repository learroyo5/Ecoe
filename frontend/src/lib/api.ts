import type {
  ActiveCheckin,
  AssessmentTool,
  DashboardSummary,
  ECOEEvent,
  ECOEResult,
  EvaluatorContext,
  Incident,
  LiveSession,
  MediaAsset,
  PilotRun,
  ResultsResponse,
  SimulatedPatient,
  StaffAssignment,
  Station,
  StationBank,
  StationTemplate,
  Student,
  StudentAccessContext,
} from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "/api";

async function request<T>(
  path: string,
  options: RequestInit = {},
  token?: string | null,
): Promise<T> {
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (token && token !== "cookie-session") {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
    cache: "no-store",
    credentials: "include",
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

type LoginResponse = { access_token?: string | null; user: { id: number; email: string; full_name: string; role: string } };
type MeResponse = { id: number; email: string; full_name: string; role: string };
type ImportResult = { imported: number; skipped: number };
type MutationResult = { saved: boolean; record_id?: number; response_id?: number };
type ConfirmCheckinResult = Record<string, unknown> & { checkin_id: number };
type DeletedResult = { deleted: boolean };

export const api = {
  login: (email: string, password: string) =>
    request<LoginResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  logout: () => request<{ logged_out: boolean }>("/auth/logout", { method: "POST" }),
  me: (token?: string | null) => request<MeResponse>("/auth/me", {}, token),

  // ECOE
  listECOE: (token: string) => request<ECOEEvent[]>("/ecoe", {}, token),
  ecoe: (eventId: number, token: string) => request<ECOEEvent>(`/ecoe/${eventId}`, {}, token),
  createECOE: (payload: Record<string, unknown>, token: string) =>
    request<ECOEEvent>("/ecoe", { method: "POST", body: JSON.stringify(payload) }, token),
  updateECOE: (eventId: number, payload: Record<string, unknown>, token: string) =>
    request<ECOEEvent>(`/ecoe/${eventId}`, { method: "PUT", body: JSON.stringify(payload) }, token),
  duplicateECOE: (eventId: number, payload: { name?: string; new_date?: string; copy_evaluators?: boolean }, token: string) =>
    request<ECOEEvent>(`/ecoe/${eventId}/duplicate`, { method: "POST", body: JSON.stringify(payload) }, token),
  dashboard: (eventId: number, token: string) => request<DashboardSummary>(`/dashboard/${eventId}`, {}, token),
  updateECOETiming: (eventId: number, payload: { station_time_minutes: number; transition_time_minutes: number; sync_existing_stations: boolean }, token: string) =>
    request<ECOEEvent>(`/ecoe/${eventId}/timing`, { method: "PATCH", body: JSON.stringify(payload) }, token),
  validation: (eventId: number, token: string) => request<Record<string, unknown>>(`/validation/${eventId}`, {}, token),

  // Students
  students: (eventId: number, token: string, page: number = 1, pageSize: number = 50) => request<Student[]>(`/students/${eventId}?page=${page}&page_size=${pageSize}`, {}, token),
  createStudent: (payload: Record<string, unknown>, token: string) =>
    request<Student>("/students", { method: "POST", body: JSON.stringify(payload) }, token),
  updateStudentStatus: (studentId: number, payload: { is_active: boolean }, token: string) =>
    request<Student>(`/students/${studentId}/status`, { method: "PATCH", body: JSON.stringify(payload) }, token),
  deleteStudent: (studentId: number, token: string) =>
    request<DeletedResult>(`/students/${studentId}`, { method: "DELETE" }, token),
  deduplicateStudentsByRut: (eventId: number, token: string) =>
    request<{ removed: number }>(`/students/${eventId}/deduplicate-rut`, { method: "POST" }, token),
  renumberStudents: (eventId: number, token: string) =>
    request<{ updated: number }>(`/students/${eventId}/renumber`, { method: "POST" }, token),
  importStudents: (eventId: number, file: File, token: string) => {
    const formData = new FormData();
    formData.append("file", file);
    return request<ImportResult>(`/students/import?ecoe_event_id=${eventId}`, { method: "POST", body: formData }, token);
  },

  // Staff
  staff: (eventId: number, token: string) => request<StaffAssignment[]>(`/staff/${eventId}`, {}, token),
  createStaff: (payload: Record<string, unknown>, token: string) =>
    request<StaffAssignment>("/staff", { method: "POST", body: JSON.stringify(payload) }, token),
  updateStaff: (staffId: number, payload: { role_code: string; station_ids: number[] }, token: string) =>
    request<StaffAssignment>(`/staff/${staffId}`, { method: "PATCH", body: JSON.stringify(payload) }, token),
  deleteStaff: (staffId: number, token: string) =>
    request<DeletedResult>(`/staff/${staffId}`, { method: "DELETE" }, token),
  deduplicateStaffByEmail: (eventId: number, token: string) =>
    request<{ removed: number }>(`/staff/${eventId}/deduplicate-email`, { method: "POST" }, token),
  importStaff: (eventId: number, file: File, token: string) => {
    const formData = new FormData();
    formData.append("file", file);
    return request<ImportResult>(`/staff/import?ecoe_event_id=${eventId}`, { method: "POST", body: formData }, token);
  },

  // Evaluator
  evaluatorContext: (eventId: number, token: string) => request<EvaluatorContext>(`/evaluator/context/${eventId}`, {}, token),
  confirmStationCheckin: (payload: { ecoe_event_id: number; station_id: number; ecoe_number: string }, token: string) =>
    request<ConfirmCheckinResult>("/station-checkins/confirm", { method: "POST", body: JSON.stringify(payload) }, token),
  submitEvaluator: (payload: Record<string, unknown>, token: string) =>
    request<MutationResult>("/evaluator/submit", { method: "POST", body: JSON.stringify(payload) }, token),

  // Student access
  studentAccess: (payload: { ecoe_event_id: number; ecoe_number: string }, token: string) =>
    request<StudentAccessContext>("/student/access", { method: "POST", body: JSON.stringify(payload) }, token),
  submitStudent: (payload: Record<string, unknown>, token: string) =>
    request<MutationResult>("/student/submit", { method: "POST", body: JSON.stringify(payload) }, token),

  // Station Bank
  stationBank: (token: string) => request<StationBank[]>("/station-bank", {}, token),
  createStationBank: (payload: Record<string, unknown>, token: string) =>
    request<StationBank>("/station-bank", { method: "POST", body: JSON.stringify(payload) }, token),
  updateStationBank: (bankStationId: number, payload: Record<string, unknown>, token: string) =>
    request<StationBank>(`/station-bank/${bankStationId}`, { method: "PUT", body: JSON.stringify(payload) }, token),
  updateStationBankStatus: (bankStationId: number, payload: { status: string }, token: string) =>
    request<StationBank>(`/station-bank/${bankStationId}/status`, { method: "PATCH", body: JSON.stringify(payload) }, token),

  // Stations
  stations: (eventId: number, token: string) => request<Station[]>(`/stations/${eventId}`, {}, token),
  createStation: (payload: Record<string, unknown>, token: string) =>
    request<Station>("/stations", { method: "POST", body: JSON.stringify(payload) }, token),
  updateStation: (stationId: number, payload: Record<string, unknown>, token: string) =>
    request<Station>(`/stations/${stationId}`, { method: "PUT", body: JSON.stringify(payload) }, token),
  deleteStation: (stationId: number, token: string) =>
    request<{ deleted: boolean }>(`/stations/${stationId}`, { method: "DELETE" }, token),

  // Media
  media: (stationId: number, token: string) => request<MediaAsset[]>(`/media/${stationId}`, {}, token),
  deleteMedia: (assetId: number, token: string) =>
    request<DeletedResult & { asset_id: number }>(`/media/${assetId}`, { method: "DELETE" }, token),
  mediaFile: (assetId: number, token: string) => request<Blob>(`/media/file/${assetId}`, {}, token),
  uploadMedia: (
    payload: { ecoe_event_id: number; station_id?: number | null; target_viewer?: string; file: File },
    token: string,
  ) => {
    const formData = new FormData();
    formData.append("file", payload.file);
    const stationId = payload.station_id ? `&station_id=${payload.station_id}` : "";
    const targetViewer = payload.target_viewer ?? "estudiante";
    return request<MediaAsset>(
      `/media/upload?ecoe_event_id=${payload.ecoe_event_id}${stationId}&target_viewer=${targetViewer}`,
      { method: "POST", body: formData },
      token,
    );
  },

  // Templates & Instruments
  templates: (token: string) => request<StationTemplate[]>("/templates", {}, token),
  createTemplate: (payload: Record<string, unknown>, token: string) =>
    request<StationTemplate>("/templates", { method: "POST", body: JSON.stringify(payload) }, token),
  instruments: (token: string) => request<AssessmentTool[]>("/instruments", {}, token),
  createInstrument: (payload: Record<string, unknown>, token: string) =>
    request<AssessmentTool>("/instruments", { method: "POST", body: JSON.stringify(payload) }, token),
  simulatedPatients: (token: string) => request<SimulatedPatient[]>("/simulated-patients", {}, token),
  createSimulatedPatient: (payload: Record<string, unknown>, token: string) =>
    request<SimulatedPatient>("/simulated-patients", { method: "POST", body: JSON.stringify(payload) }, token),

  // Pilotage
  pilotage: (eventId: number, token: string) => request<PilotRun[]>(`/pilotage/${eventId}`, {}, token),
  createPilotage: (payload: Record<string, unknown>, token: string) =>
    request<PilotRun>("/pilotage", { method: "POST", body: JSON.stringify(payload) }, token),
  archivePilotage: (id: number, token: string) =>
    request<{ archived: boolean }>(`/pilotage/${id}/archive`, { method: "POST" }, token),

  // Live
  live: (eventId: number, token: string) => request<LiveSession>(`/live/${eventId}`, {}, token),
  liveControl: (payload: { ecoe_event_id: number; action: string }, token: string) =>
    request<LiveSession>("/live/control", { method: "POST", body: JSON.stringify(payload) }, token),

  // Results
  results: (eventId: number, token: string) => request<ResultsResponse>(`/results/${eventId}`, {}, token),

  // Incidents
  incidents: (eventId: number, token: string) => request<Incident[]>(`/incidents/${eventId}`, {}, token),
  createIncident: (payload: { ecoe_event_id: number; station_id?: number | null; title: string; detail?: string; severity?: string }, token: string) =>
    request<Incident>("/incidents", { method: "POST", body: JSON.stringify(payload) }, token),
  resolveIncident: (incidentId: number, resolved: boolean, token: string) =>
    request<Incident>(`/incidents/${incidentId}/resolve`, { method: "PATCH", body: JSON.stringify({ resolved }) }, token),
};
