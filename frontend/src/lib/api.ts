import type {
  AssessmentTool,
  DashboardSummary,
  ECOEEvent,
  EvaluatorContext,
  Incident,
  LiveSession,
  MediaAsset,
  Paginated,
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

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  // Session lives in an httpOnly cookie set by the backend; no bearer token
  // is ever held or sent from the client.
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
    cache: "no-store",
    credentials: "include",
  });

  if (!response.ok) {
    const text = await response.text();
    let detail = text || "No se pudo completar la solicitud";
    try {
      const parsed = JSON.parse(text);
      if (parsed.detail) detail = parsed.detail;
    } catch { /* not JSON, use raw text */ }
    throw new Error(detail);
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
type UserRow = { id: number; email: string; full_name: string; role_code: string; is_active: boolean };

export const api = {
  login: (email: string, password: string) =>
    request<LoginResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  logout: () => request<{ logged_out: boolean }>("/auth/logout", { method: "POST" }),
  me: () => request<MeResponse>("/auth/me"),

  // ECOE
  listECOE: () => request<ECOEEvent[]>("/ecoe"),
  ecoe: (eventId: number) => request<ECOEEvent>(`/ecoe/${eventId}`),
  createECOE: (payload: Record<string, unknown>) =>
    request<ECOEEvent>("/ecoe", { method: "POST", body: JSON.stringify(payload) }),
  updateECOE: (eventId: number, payload: Record<string, unknown>) =>
    request<ECOEEvent>(`/ecoe/${eventId}`, { method: "PUT", body: JSON.stringify(payload) }),
  duplicateECOE: (eventId: number, payload: { name?: string; new_date?: string; copy_evaluators?: boolean }) =>
    request<ECOEEvent>(`/ecoe/${eventId}/duplicate`, { method: "POST", body: JSON.stringify(payload) }),
  dashboard: (eventId: number) => request<DashboardSummary>(`/dashboard/${eventId}`),
  updateECOETiming: (eventId: number, payload: { station_time_minutes: number; transition_time_minutes: number; sync_existing_stations: boolean }) =>
    request<ECOEEvent>(`/ecoe/${eventId}/timing`, { method: "PATCH", body: JSON.stringify(payload) }),
  validation: (eventId: number) => request<Record<string, unknown>>(`/validation/${eventId}`),

  // Users
  listUsers: () => request<UserRow[]>("/users"),
  createUser: (payload: { email: string; full_name: string; password: string; role_code: string }) =>
    request<UserRow>("/users", { method: "POST", body: JSON.stringify(payload) }),
  updateUser: (userId: number, payload: { full_name?: string; role_code?: string; password?: string; is_active?: boolean }) =>
    request<UserRow>(`/users/${userId}`, { method: "PATCH", body: JSON.stringify(payload) }),

  // Students
  students: (eventId: number, page: number = 1, pageSize: number = 50) =>
    request<Paginated<Student>>(`/students/${eventId}?page=${page}&page_size=${pageSize}`),
  createStudent: (payload: Record<string, unknown>) =>
    request<Student>("/students", { method: "POST", body: JSON.stringify(payload) }),
  updateStudentStatus: (studentId: number, payload: { is_active: boolean }) =>
    request<Student>(`/students/${studentId}/status`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteStudent: (studentId: number) =>
    request<DeletedResult>(`/students/${studentId}`, { method: "DELETE" }),
  deduplicateStudentsByRut: (eventId: number) =>
    request<{ removed: number }>(`/students/${eventId}/deduplicate-rut`, { method: "POST" }),
  renumberStudents: (eventId: number) =>
    request<{ updated: number }>(`/students/${eventId}/renumber`, { method: "POST" }),
  importStudents: (eventId: number, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return request<ImportResult>(`/students/import?ecoe_event_id=${eventId}`, { method: "POST", body: formData });
  },

  // Staff
  staff: (eventId: number, page: number = 1, pageSize: number = 50) =>
    request<Paginated<StaffAssignment>>(`/staff/${eventId}?page=${page}&page_size=${pageSize}`),
  createStaff: (payload: Record<string, unknown>) =>
    request<StaffAssignment>("/staff", { method: "POST", body: JSON.stringify(payload) }),
  updateStaff: (staffId: number, payload: { role_code: string; station_ids: number[] }) =>
    request<StaffAssignment>(`/staff/${staffId}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteStaff: (staffId: number) =>
    request<DeletedResult>(`/staff/${staffId}`, { method: "DELETE" }),
  deduplicateStaffByEmail: (eventId: number) =>
    request<{ removed: number }>(`/staff/${eventId}/deduplicate-email`, { method: "POST" }),
  importStaff: (eventId: number, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return request<ImportResult>(`/staff/import?ecoe_event_id=${eventId}`, { method: "POST", body: formData });
  },

  // Evaluator
  evaluatorContext: (eventId: number) => request<EvaluatorContext>(`/evaluator/context/${eventId}`),
  confirmStationCheckin: (payload: { ecoe_event_id: number; station_id: number; ecoe_number: string }) =>
    request<ConfirmCheckinResult>("/station-checkins/confirm", { method: "POST", body: JSON.stringify(payload) }),
  submitEvaluator: (payload: Record<string, unknown>) =>
    request<MutationResult>("/evaluator/submit", { method: "POST", body: JSON.stringify(payload) }),

  // Student access
  studentAccess: (payload: { ecoe_event_id: number; ecoe_number: string }) =>
    request<StudentAccessContext>("/student/access", { method: "POST", body: JSON.stringify(payload) }),
  submitStudent: (payload: Record<string, unknown>) =>
    request<MutationResult>("/student/submit", { method: "POST", body: JSON.stringify(payload) }),

  // Station Bank
  stationBank: () => request<StationBank[]>("/station-bank"),
  createStationBank: (payload: Record<string, unknown>) =>
    request<StationBank>("/station-bank", { method: "POST", body: JSON.stringify(payload) }),
  updateStationBank: (bankStationId: number, payload: Record<string, unknown>) =>
    request<StationBank>(`/station-bank/${bankStationId}`, { method: "PUT", body: JSON.stringify(payload) }),
  updateStationBankStatus: (bankStationId: number, payload: { status: string }) =>
    request<StationBank>(`/station-bank/${bankStationId}/status`, { method: "PATCH", body: JSON.stringify(payload) }),

  // Stations
  stations: (eventId: number) => request<Station[]>(`/stations/${eventId}`),
  createStation: (payload: Record<string, unknown>) =>
    request<Station>("/stations", { method: "POST", body: JSON.stringify(payload) }),
  updateStation: (stationId: number, payload: Record<string, unknown>) =>
    request<Station>(`/stations/${stationId}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteStation: (stationId: number) =>
    request<{ deleted: boolean }>(`/stations/${stationId}`, { method: "DELETE" }),

  // Media
  media: (stationId: number) => request<MediaAsset[]>(`/media/${stationId}`),
  deleteMedia: (assetId: number) =>
    request<DeletedResult & { asset_id: number }>(`/media/${assetId}`, { method: "DELETE" }),
  mediaFile: (assetId: number) => request<Blob>(`/media/file/${assetId}`),
  uploadMedia: (payload: { ecoe_event_id: number; station_id?: number | null; target_viewer?: string; file: File }) => {
    const formData = new FormData();
    formData.append("file", payload.file);
    const stationId = payload.station_id ? `&station_id=${payload.station_id}` : "";
    const targetViewer = payload.target_viewer ?? "estudiante";
    return request<MediaAsset>(
      `/media/upload?ecoe_event_id=${payload.ecoe_event_id}${stationId}&target_viewer=${targetViewer}`,
      { method: "POST", body: formData },
    );
  },

  // Templates & Instruments
  templates: () => request<StationTemplate[]>("/templates"),
  createTemplate: (payload: Record<string, unknown>) =>
    request<StationTemplate>("/templates", { method: "POST", body: JSON.stringify(payload) }),
  instruments: () => request<AssessmentTool[]>("/instruments"),
  createInstrument: (payload: Record<string, unknown>) =>
    request<AssessmentTool>("/instruments", { method: "POST", body: JSON.stringify(payload) }),
  simulatedPatients: () => request<SimulatedPatient[]>("/simulated-patients"),
  createSimulatedPatient: (payload: Record<string, unknown>) =>
    request<SimulatedPatient>("/simulated-patients", { method: "POST", body: JSON.stringify(payload) }),

  // Pilotage
  pilotage: (eventId: number) => request<PilotRun[]>(`/pilotage/${eventId}`),
  createPilotage: (payload: Record<string, unknown>) =>
    request<PilotRun>("/pilotage", { method: "POST", body: JSON.stringify(payload) }),
  archivePilotage: (id: number) =>
    request<{ archived: boolean }>(`/pilotage/${id}/archive`, { method: "POST" }),

  // Live
  live: (eventId: number) => request<LiveSession>(`/live/${eventId}`),
  liveControl: (payload: { ecoe_event_id: number; action: string }) =>
    request<LiveSession>("/live/control", { method: "POST", body: JSON.stringify(payload) }),

  // Results
  results: (eventId: number) => request<ResultsResponse>(`/results/${eventId}`),

  // Incidents
  incidents: (eventId: number, page: number = 1, pageSize: number = 50) =>
    request<Paginated<Incident>>(`/incidents/${eventId}?page=${page}&page_size=${pageSize}`),
  createIncident: (payload: { ecoe_event_id: number; station_id?: number | null; title: string; detail?: string; severity?: string }) =>
    request<Incident>("/incidents", { method: "POST", body: JSON.stringify(payload) }),
  resolveIncident: (incidentId: number, resolved: boolean) =>
    request<Incident>(`/incidents/${incidentId}/resolve`, { method: "PATCH", body: JSON.stringify({ resolved }) }),
};
