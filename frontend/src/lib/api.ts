import type {
  AssessmentTool,
  DashboardSummary,
  ECOEEvent,
  EvaluatorContext,
  EvaluatorDraftRow,
  GradeResponseResult,
  GradingListResult,
  Incident,
  LiveSession,
  MediaAsset,
  Paginated,
  PilotRun,
  PsychometricsResponse,
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
  evaluatorContext: (eventId: number, stationId?: number) =>
    request<EvaluatorContext>(
      `/evaluator/context/${eventId}${stationId ? `?station_id=${stationId}` : ""}`,
    ),
  confirmStationCheckin: (payload: { ecoe_event_id: number; station_id: number; ecoe_number: string }) =>
    request<ConfirmCheckinResult>("/station-checkins/confirm", { method: "POST", body: JSON.stringify(payload) }),
  submitEvaluator: (payload: Record<string, unknown>) =>
    request<MutationResult>("/evaluator/submit", { method: "POST", body: JSON.stringify(payload) }),
  // OPT-20 F3 (D3): autoguardado server-side del registro del evaluador a
  // medio llenar. El registro parcial ES la fila (is_draft=True); se promueve
  // a definitiva al enviar o al finalizarla por contingencia.
  evaluatorDraft: (payload: {
    ecoe_event_id: number;
    station_id: number;
    student_id: number;
    checkin_id?: number;
    evaluator_name: string;
    score_obtained: number;
    observation: string;
    answers: Record<string, unknown>;
  }) =>
    request<{ saved: boolean; record_id: number; is_draft: boolean; updated_at: string | null }>(
      "/evaluator/draft",
      { method: "PUT", body: JSON.stringify(payload) },
    ),
  // Coordinación: borradores de evaluador pendientes de finalizar y su cierre
  // por contingencia (finaliza el borrador existente si lo hay).
  pendingEvaluatorDrafts: (eventId: number) =>
    request<{ drafts: EvaluatorDraftRow[] }>(`/contingency/evaluator-drafts/${eventId}`),
  finalizeEvaluatorRecord: (payload: Record<string, unknown>) =>
    request<MutationResult & { by_contingency?: boolean; finalized_draft?: boolean }>(
      "/contingency/evaluator-record",
      { method: "POST", body: JSON.stringify(payload) },
    ),

  // Student access
  studentAccess: (payload: { ecoe_event_id: number; ecoe_number: string }) =>
    request<StudentAccessContext>("/student/access", { method: "POST", body: JSON.stringify(payload) }),
  submitStudent: (payload: Record<string, unknown>) =>
    request<MutationResult>("/student/submit", { method: "POST", body: JSON.stringify(payload) }),
  // OPT-20 F2: autoguardado server-side del borrador del check-in activo
  // (mejor esfuerzo; el localStorage sigue siendo el respaldo local).
  studentDraft: (payload: {
    ecoe_event_id: number;
    station_id: number;
    student_id: number;
    checkin_id?: number;
    answers: Record<string, unknown>;
  }) =>
    request<{ saved: boolean; updated_at: string | null }>("/student/draft", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),

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
  // OPT-20 F2: autoguardado server-side del borrador (mejor esfuerzo).
  kioskDraft: (token: string, payload: { checkin_id: number; answers: Record<string, unknown> }) =>
    request<{ saved: boolean; updated_at: string | null }>("/kiosk/draft", {
      method: "PUT",
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
  instruments: (eventId: number, opts?: { includeArchived?: boolean }) =>
    request<AssessmentTool[]>(
      `/instruments?ecoe_event_id=${eventId}${opts?.includeArchived ? "&include_archived=true" : ""}`,
    ),
  instrument: (eventId: number, id: number) =>
    request<AssessmentTool>(`/instruments/${id}?ecoe_event_id=${eventId}`),
  createInstrument: (eventId: number, payload: Record<string, unknown>) =>
    request<AssessmentTool>(`/instruments?ecoe_event_id=${eventId}`, { method: "POST", body: JSON.stringify(payload) }),
  updateInstrument: (eventId: number, id: number, payload: Record<string, unknown>) =>
    request<AssessmentTool>(`/instruments/${id}?ecoe_event_id=${eventId}`, { method: "PATCH", body: JSON.stringify(payload) }),
  archiveInstrument: (eventId: number, id: number) =>
    request<AssessmentTool>(`/instruments/${id}?ecoe_event_id=${eventId}`, { method: "DELETE" }),
  restoreInstrument: (eventId: number, id: number) =>
    request<AssessmentTool>(`/instruments/${id}/restore?ecoe_event_id=${eventId}`, { method: "POST" }),
  purgeInstrument: (eventId: number, id: number) =>
    request<{ deleted: boolean }>(`/instruments/${id}/purge?ecoe_event_id=${eventId}`, { method: "DELETE" }),
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
    request<GradingListResult>(`/grading/${eventId}`),
  gradeResponse: (responseId: number, scores: Record<string, number>) =>
    request<GradeResponseResult>(
      `/grading/responses/${responseId}`,
      { method: "POST", body: JSON.stringify({ scores }) },
    ),

  // Live
  live: (eventId: number) => request<LiveSession>(`/live/${eventId}`),
  liveControl: (payload: { ecoe_event_id: number; action: string }) =>
    request<LiveSession>("/live/control", { method: "POST", body: JSON.stringify(payload) }),

  // Results
  results: (eventId: number) => request<ResultsResponse>(`/results/${eventId}`),

  // Analítica psicométrica (OPT-18)
  psychometrics: (eventId: number, mode: "ejecucion" | "pilotaje" = "ejecucion") =>
    request<PsychometricsResponse>(`/analytics/${eventId}/psychometrics?mode=${mode}`),

  // Incidents
  incidents: (eventId: number, page: number = 1, pageSize: number = 50) =>
    request<Paginated<Incident>>(`/incidents/${eventId}?page=${page}&page_size=${pageSize}`),
  createIncident: (payload: { ecoe_event_id: number; station_id?: number | null; title: string; detail?: string; severity?: string }) =>
    request<Incident>("/incidents", { method: "POST", body: JSON.stringify(payload) }),
  resolveIncident: (incidentId: number, resolved: boolean) =>
    request<Incident>(`/incidents/${incidentId}/resolve`, { method: "PATCH", body: JSON.stringify({ resolved }) }),
};

/**
 * OPT-20 F2: el backend puede rechazar un envío (manual o automático) porque
 * la respuesta ya existe — el barrido server-side ganó la carrera. Para el
 * cliente eso es un éxito: la respuesta quedó registrada. Detectamos el caso
 * por el texto del `detail` (400/409 "ya fue enviada").
 */
export function isAlreadySubmittedError(error: unknown): boolean {
  return (
    error instanceof Error &&
    /ya (fue |había sido )?enviada|already submitted/i.test(error.message)
  );
}
