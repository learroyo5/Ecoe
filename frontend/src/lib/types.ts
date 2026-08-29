/** Core domain types for the ECOE platform. */

/** Shape returned by the backend's paginate_query (students, staff, incidents). */
export type Paginated<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
};

export type UserSession = {
  id: number;
  email: string;
  full_name: string;
  role: string;
};

export type ECOEEvent = {
  id: number;
  name: string;
  date: string;
  course_name: string;
  school_name: string;
  responsible_teacher: string;
  contact_email: string;
  circuit_mode: string;
  total_stations: number;
  station_time_minutes: number;
  transition_time_minutes: number;
  total_students: number;
  total_groups: number;
  passing_reference_percent: number;
  status: string;
  created_at: string;
  updated_at: string;
};

export type Student = {
  id: number;
  ecoe_event_id: number;
  name: string;
  last_name: string;
  rut: string;
  email: string;
  ecoe_number: string;
  group_name: string;
  circuit_name: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type StaffAssignment = {
  id: number;
  ecoe_event_id: number;
  name: string;
  last_name: string;
  email: string;
  role_code: string;
  station_ids: number[];
  created_at: string;
  updated_at: string;
};

export type Station = {
  id: number;
  ecoe_event_id: number;
  template_id: number | null;
  assessment_tool_id: number | null;
  simulated_patient_id: number | null;
  station_number: number;
  name: string;
  station_type: string;
  circuit_name: string;
  station_time_minutes: number;
  transition_time_minutes: number;
  expected_outcomes: string;
  student_activity: string;
  student_station_instruction: string;
  pre_entry_instruction: string;
  evaluator_instruction: string;
  requires_evaluator: boolean;
  requires_student_form: boolean;
  requires_deferred_grading: boolean;
  uses_multimedia: boolean;
  uses_simulated_patient: boolean;
  uses_physical_resources: boolean;
  max_score: number;
  materials: string;
  clinical_equipment: string;
  simulator: string;
  ambience: string;
  multimedia_notes: string;
  student_form_definition: Record<string, unknown>;
  contingency_ready: boolean;
  status: string;
};

export type AssessmentTool = {
  id: number;
  name: string;
  tool_type: string;
  max_score: number;
  free_observation: boolean;
  created_by?: string | null;
  origin_event_id?: number | null;
  archived?: boolean;
  reference_count?: number;
  items?: AssessmentItem[];
};

export type AssessmentItem = {
  id: number;
  label: string;
  score_per_item: number;
  order_index: number;
};

export type StationTemplate = {
  id: number;
  name: string;
  category: string;
  description: string;
  default_configuration: Record<string, unknown>;
};

export type SimulatedPatient = {
  id: number;
  character_name: string;
  summary_profile: string;
  base_story: string;
  key_answers: string;
  emotional_tone: string;
  special_instructions: string;
};

export type StationBank = {
  id: number;
  template_id: number | null;
  assessment_tool_id: number | null;
  simulated_patient_id: number | null;
  name: string;
  station_type: string;
  circuit_name: string;
  expected_outcomes: string;
  student_activity: string;
  pre_entry_instruction: string;
  evaluator_instruction: string;
  requires_evaluator: boolean;
  requires_student_form: boolean;
  requires_deferred_grading: boolean;
  uses_multimedia: boolean;
  uses_simulated_patient: boolean;
  max_score: number;
  status: string;
};

export type PilotRun = {
  id: number;
  ecoe_event_id: number;
  name: string;
  scope: string;
  archived: boolean;
  created_at: string;
  updated_at: string;
};

export type LiveSession = {
  id: number;
  ecoe_event_id: number;
  mode: string;
  status: string;
  station_time_seconds: number;
  transition_time_seconds: number;
  current_station_index: number;
  remaining_seconds: number;
  /** Inicio de la fase actual (null si el timer no corre). */
  phase_started_at?: string | null;
  /** Reloj del servidor al momento de la respuesta: usar para offset local. */
  server_now?: string;
};

export type Incident = {
  id: number;
  ecoe_event_id: number;
  station_id: number | null;
  title: string;
  detail: string;
  severity: string;
  resolved: boolean;
  resolved_at: string | null;
  created_at: string;
};

export type MediaAsset = {
  id: number;
  filename: string;
  original_name: string;
  content_type: string;
  target_viewer: string;
  station_id: number | null;
  file_url: string;
};

export type DashboardSummary = {
  active_ecoe: {
    id: number;
    name: string;
    status: string;
    date: string;
    course_name: string;
  };
  totals: Record<string, number>;
  validation: ECOEValidation;
  timeline: Array<{ label: string; status: string; circuit: string }>;
  live_panel: {
    status: string;
    current_station_index: number;
    remaining_seconds: number;
  };
};

export type ECOEValidation = {
  students_count: number;
  station_count: number;
  pilot_count: number;
  complete_stations: number;
  can_pilot: boolean;
  can_publish: boolean;
  can_start_live: boolean;
  warnings: string[];
  blockers: string[];
  pilot_checks: CheckItem[];
  publication_checks: CheckItem[];
  live_checks: CheckItem[];
  station_issues: StationIssue[];
};

export type CheckItem = {
  label: string;
  ok: boolean;
  detail: string;
};

export type StationIssue = {
  station_id: number;
  station_number: number;
  station_name: string;
  circuit_name: string;
  ready_for_pilot: boolean;
  blockers: string[];
  warnings: string[];
};

export type EvaluatorContext = {
  assignment: StaffAssignment | null;
  stations: Station[];
  selected_station_id: number | null;
  active_checkin: ActiveCheckin | null;
};

export type ActiveCheckin = {
  id: number;
  station_id: number;
  student_id: number;
  status: string;
  student_name: string;
  student_ecoe_number: string;
  station_name: string;
  station_number: number;
  assessment_tool: Record<string, unknown> | null;
  evaluator_instruction: string;
  confirmed_at: string;
  station_time_minutes: number;
  /** OPT-20 F2: deadline autoritativo derivado de la fase del LiveSession
   *  (fin de la fase de estación en curso); `null` mientras el reloj central
   *  está en pausa. */
  submission_deadline?: string | null;
  /** OPT-20 F2: deadline del evaluador — incluye la fase de transición en
   *  curso; `null` en pausa. */
  evaluator_deadline?: string | null;
  evaluator_submission_exists: boolean;
  student_response_exists: boolean;
};

/** OPT-20 F3 (D3): un EvaluatorRecord que quedó como borrador al vencer la
 *  fase; coordinación lo finaliza en la ventana de contingencia. */
export type EvaluatorDraftRow = {
  record_id: number;
  station_id: number;
  station_number: number | null;
  station_name: string;
  student_id: number;
  student_ecoe_number: string;
  student_name: string;
  score_obtained: number;
  max_score: number;
  evaluator_name: string;
  observation: string;
  updated_at: string | null;
};

export type StudentAccessContext = {
  checkin_id: number;
  student_id: number;
  student_name: string;
  student_ecoe_number: string;
  station_id: number;
  station_name: string;
  station_number: number;
  student_activity: string;
  pre_entry_instruction: string;
  student_station_instruction: string;
  student_form_definition: Record<string, unknown>;
  media_assets: MediaAsset[];
  station_time_minutes: number;
  confirmed_at: string;
  student_response_exists: boolean;
  server_now?: string;
  /** OPT-20 F2: deadline autoritativo derivado de la fase del LiveSession;
   *  `null` mientras el reloj central está en pausa. */
  submission_deadline?: string | null;
  /** OPT-20 F1: snapshot del reloj central para la primera pintura y el
   *  fallback sin WebSocket. */
  live_status?: string | null;
  current_phase_ends_at?: string | null;
  paused?: boolean;
};

export type TraceabilityReport = {
  summary: {
    active_students: number;
    stations: number;
    expected_evaluations: number;
    expected_student_submissions: number;
    confirmed_checkins: number;
    evaluator_submissions: number;
    student_submissions: number;
    pending_evaluator_drafts?: number;
    /** OPT-20 F4 (D4): autoenvíos del barrido sin contenido. */
    blank_auto_submissions?: number;
    pilot_runs: number;
  };
  student_traceability: StudentTraceability[];
  station_traceability: StationTraceability[];
  activity_log: ActivityLogEntry[];
};

export type StudentTraceability = {
  id: number;
  student_id: number;
  ecoe_number: string;
  student_name: string;
  checkins_confirmed: number;
  evaluator_submissions: number;
  student_submissions: number;
  missing_evaluations: number;
  missing_student_submissions: number;
  pending_evaluator_drafts?: number;
  /** OPT-20 F4 (D4): respuestas autoenviadas en blanco por el barrido. */
  blank_auto_submissions?: number;
  completion_status: string;
  last_activity_at: string | null;
  total_score: number;
  percentage: number;
  equivalent_grade: number;
};

export type StationTraceability = {
  id: number;
  station_id: number;
  station_number: number;
  station_name: string;
  circuit_name: string;
  status: string;
  assigned_evaluator: string;
  checkins_count: number;
  evaluations_count: number;
  student_submissions_count: number;
  pending_evaluator_drafts?: number;
  /** OPT-20 F4 (D4): respuestas autoenviadas en blanco por el barrido. */
  blank_auto_submissions?: number;
  last_activity_at: string | null;
};

export type ActivityLogEntry = {
  timestamp: string;
  type: string;
  label: string;
  detail: string;
  actor: string;
  mode: string;
  /** OPT-20 F4 (D4): solo en entradas de tipo `respuesta_estudiante`. */
  submission_kind?: string;
  answered?: boolean;
};

export type ECOEResult = {
  student_id: number;
  student_name: string;
  ecoe_number: string;
  total_score: number;
  max_score: number;
  percentage: number;
  equivalent_grade: number;
};

export type ResultsResponse = {
  results: ECOEResult[];
  /** true cuando el ECOE está cerrado/archivado y el payload sirve el
   *  snapshot consolidado (`ECOEResult`) en vez de recalcular en vivo. */
  frozen: boolean;
  /** ISO 8601 de la consolidación (`ECOEResult.updated_at`); null si el
   *  evento aún no está congelado o se cerró antes de poblar el snapshot. */
  consolidated_at: string | null;
} & TraceabilityReport;
