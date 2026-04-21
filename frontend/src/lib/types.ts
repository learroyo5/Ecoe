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

export type DashboardSummary = {
  active_ecoe: {
    id: number;
    name: string;
    status: string;
    date: string;
    course_name: string;
  };
  totals: Record<string, number>;
  validation: {
    can_pilot: boolean;
    can_publish: boolean;
    can_start_live: boolean;
    warnings: string[];
    students_count: number;
    station_count: number;
    pilot_count: number;
    complete_stations: number;
  };
  timeline: Array<{ label: string; status: string; circuit: string }>;
  live_panel: {
    status: string;
    current_station_index: number;
    remaining_seconds: number;
  };
};
