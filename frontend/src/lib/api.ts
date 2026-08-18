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
      if (typeof parsed.detail === "string") {
        detail = parsed.detail;
      } else if (Array.isArray(parsed.detail)) {
        // FastAPI validation errors arrive as a list of objects; stringifying
        // them directly renders "[object Object]".
        const messages = parsed.detail
          .map((item: { msg?: string; loc?: (string | number)[] }) => {
            const field = (item.loc ?? []).filter((part) => part !== "body").join(".");
            return field ? `${field}: ${item.msg ?? ""}` : item.msg ?? "";
          })
          .filter(Boolean);
        if (messages.length > 0) detail = messages.join(" · ");
      }
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
type UserRow = { id: number; email: string; full_name: string; role_code: string; is_active: boolean; account_status: string };
type ECOEAdminRow = { permission_id: number; user_id: number; email: string; full_name: string };

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
  eventRoles: (eventId: number) => request<{ roles: string[]; is_global_admin: boolean }>(`/ecoe/${eventId}/roles/me`),
  eventAdmins: (eventId: number) => request<ECOEAdminRow[]>(`/ecoe/${eventId}/admins`),
  grantEventAdmin: (eventId: number, userId: number) =>
    request<{ granted: boolean }>(`/ecoe/${eventId}/admins/${userId}`, { method: "POST" }),
  revokeEventAdmin: (eventId: number, userId: number) =>
    request<{ revoked: boolean }>(`/ecoe/${eventId}/admins/${userId}`, { method: "DELETE" }),
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
  lookupEventMember: (eventId: number, email: string) =>
    request<{ exists: boolean; full_name?: string; account_status?: string; assigned_to_event: boolean }>(
      `/event-members/lookup?ecoe_event_id=${eventId}&email=${encodeURIComponent(email)}`,
    ),
  inviteEventMember: (payload: Record<string, unknown>) =>
    request<{
      status: "assigned" | "invited";
      email: string;
      activation_path?: string;
      expires_at?: string;
      email_sent?: boolean;
    }>("/event-members/invite", { method: "POST", body: JSON.stringify(payload) }),
  resetEventMemberAccess: (eventId: number, email: string) =>
    request<{
      status: "reset";
      email: string;
      activation_path: string;
      expires_at: string;
      email_sent: boolean;
    }>("/event-members/reset-access", {
      method: "POST",
      body: JSON.stringify({ ecoe_event_id: eventId, email }),
    }),
  activateInvitation: (token: string, password: string) =>
    request<{ activated: boolean }>("/auth/activate-invitation", {
      method: "POST",
      body: JSON.stringify({ token, password }),
    }),

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

  // Kiosk (dispositivo compartido por estación; autentica con token propio,
  // nunca con la sesión de usuario)
  issueKioskToken: (stationId: number) =>
    request<{ token: string; kiosk_path: string; expires_at: string }>(
      `/kiosk/stations/${stationId}/token`, { method: "POST" },
    ),
  revokeKioskToken: (stationId: number) =>
    request<{ revoked: number }>(`/kiosk/stations/${stationId}/token`, { method: "DELETE" }),
  kioskContext: (token: string) =>
    request<Record<string, unknown>>("/kiosk/context", { headers: { "X-Kiosk-Token": token } }),
  kioskSubmit: (token: string, payload: { checkin_id: number; answers: Record<string, unknown> }) =>
    request<MutationResult>("/kiosk/submit", {
      method: "POST",
      headers: { "X-Kiosk-Token": token },
      body: JSON.stringify(payload),
    }),
  kioskMediaFile: (token: string, assetId: number) =>
    request<Blob>(`/kiosk/media/${assetId}`, { headers: { "X-Kiosk-Token": token } }),

  // Station Bank
  stationBank: (eventId: number) => request<StationBank[]>(`/station-bank?ecoe_event_id=${eventId}`),
  createStationBank: (eventId: number, payload: Record<string, unknown>) =>
    request<StationBank>(`/station-bank?ecoe_event_id=${eventId}`, { method: "POST", body: JSON.stringify(payload) }),
  updateStationBank: (eventId: number, bankStationId: number, payload: Record<string, unknown>) =>
    request<StationBank>(`/station-bank/${bankStationId}?ecoe_event_id=${eventId}`, { method: "PUT", body: JSON.stringify(payload) }),
  updateStationBankStatus: (eventId: number, bankStationId: number, payload: { status: string }) =>
    request<StationBank>(`/station-bank/${bankStationId}/status?ecoe_event_id=${eventId}`, { method: "PATCH", body: JSON.stringify(payload) }),

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
  templates: (eventId: number) => request<StationTemplate[]>(`/templates?ecoe_event_id=${eventId}`),
  createTemplate: (eventId: number, payload: Record<string, unknown>) =>
    request<StationTemplate>(`/templates?ecoe_event_id=${eventId}`, { method: "POST", body: JSON.stringify(payload) }),
  instruments: (eventId: number) => request<AssessmentTool[]>(`/instruments?ecoe_event_id=${eventId}`),
  createInstrument: (eventId: number, payload: Record<string, unknown>) =>
    request<AssessmentTool>(`/instruments?ecoe_event_id=${eventId}`, { method: "POST", body: JSON.stringify(payload) }),
  simulatedPatients: (eventId: number) => request<SimulatedPatient[]>(`/simulated-patients?ecoe_event_id=${eventId}`),
  createSimulatedPatient: (eventId: number, payload: Record<string, unknown>) =>
    request<SimulatedPatient>(`/simulated-patients?ecoe_event_id=${eventId}`, { method: "POST", body: JSON.stringify(payload) }),

  // Pilotage
  pilotage: (eventId: number) => request<PilotRun[]>(`/pilotage/${eventId}`),
  createPilotage: (payload: Record<string, unknown>) =>
    request<PilotRun>("/pilotage", { method: "POST", body: JSON.stringify(payload) }),
  archivePilotage: (id: number) =>
    request<{ archived: boolean }>(`/pilotage/${id}/archive`, { method: "POST" }),
  updatePilotageNotes: (id: number, notes: string) =>
    request<PilotRun>(`/pilotage/${id}/notes`, { method: "PATCH", body: JSON.stringify({ notes }) }),

  // Grading (corrección manual de formularios del estudiante)
  gradingList: (eventId: number) =>
    request<{ responses: Record<string, unknown>[]; pending_count: number }>(`/grading/${eventId}`),
  gradeResponse: (responseId: number, scores: Record<string, number>) =>
    request<{ graded: boolean; score_obtained: number; max_score: number }>(
      `/grading/responses/${responseId}`,
      { method: "POST", body: JSON.stringify({ scores }) },
    ),

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
