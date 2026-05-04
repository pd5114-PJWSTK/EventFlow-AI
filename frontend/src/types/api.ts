export type JsonObject = Record<string, unknown>;

export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
}

export interface UserMe {
  user_id: string;
  username: string;
  roles: string[];
  is_superadmin: boolean;
}

export interface ApiErrorPayload {
  detail?: string;
  error_code?: string;
  message?: string;
}

export interface ListResponse<T> {
  items: T[];
  total: number;
  limit?: number;
  offset?: number;
}

export interface EventItem {
  event_id: string;
  client_id: string;
  location_id: string;
  event_name: string;
  event_type: string;
  event_subtype?: string | null;
  description?: string | null;
  planned_start: string;
  planned_end: string;
  priority: string;
  status: string;
  attendee_count?: number | null;
  budget_estimate?: string | number | null;
  currency_code?: string | null;
  source_channel?: string | null;
  requires_transport?: boolean;
  requires_setup?: boolean;
  requires_teardown?: boolean;
  notes?: string | null;
  created_by?: string | null;
  created_by_user_id?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface LocationItem {
  location_id: string;
  name?: string | null;
  city: string;
  address_line?: string | null;
  postal_code?: string | null;
  country_code?: string | null;
  latitude?: string | number | null;
  longitude?: string | number | null;
  location_type: string;
  parking_difficulty: number;
  access_difficulty: number;
  setup_complexity_score: number;
  notes?: string | null;
  created_at?: string | null;
}

export interface PersonItem {
  person_id: string;
  full_name: string;
  role: string;
  employment_type: string;
  home_base_location_id?: string | null;
  availability_status: string;
  max_daily_hours: string | number;
  max_weekly_hours: string | number;
  cost_per_hour?: string | number | null;
  reliability_notes?: string | null;
  active: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface EquipmentItem {
  equipment_id: string;
  equipment_type_id: string;
  asset_tag?: string | null;
  serial_number?: string | null;
  status: string;
  warehouse_location_id?: string | null;
  transport_requirements?: string | null;
  replacement_available: boolean;
  hourly_cost_estimate?: string | number | null;
  purchase_date?: string | null;
  notes?: string | null;
  active: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface EquipmentTypeItem {
  equipment_type_id: string;
  type_name: string;
  category?: string | null;
  description?: string | null;
  default_setup_minutes?: number | null;
  default_teardown_minutes?: number | null;
}

export interface VehicleItem {
  vehicle_id: string;
  vehicle_name: string;
  vehicle_type: string;
  registration_number?: string | null;
  capacity_notes?: string | null;
  status: string;
  home_location_id?: string | null;
  cost_per_km?: string | number | null;
  cost_per_hour?: string | number | null;
  active: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface SkillItem {
  skill_id: string;
  skill_name: string;
  skill_category?: string | null;
  description?: string | null;
}

export interface AdminUser {
  user_id: string;
  username: string;
  roles: string[];
  is_active: boolean;
  is_superadmin: boolean;
}

export interface ModelRegistryItem {
  model_id: string;
  model_name: string;
  model_version: string;
  prediction_type: string;
  status: string;
  training_data_from?: string | null;
  training_data_to?: string | null;
  metrics: Record<string, unknown>;
  created_at: string;
}

export interface LlmStatus {
  enabled: boolean;
  configured: boolean;
  endpoint_configured: boolean;
  api_key_configured: boolean;
  deployment_configured: boolean;
  deployment?: string | null;
  mode: "llm" | "fallback";
  message: string;
}

export interface ParsedRequirement {
  requirement_type: string;
  role_required?: string | null;
  skill_id?: string | null;
  equipment_type_id?: string | null;
  vehicle_type_required?: string | null;
  quantity: string | number;
  mandatory: boolean;
  notes?: string | null;
}

export interface EventDraft {
  client_id?: string | null;
  client_name: string;
  location_id?: string | null;
  location_name: string;
  city: string;
  event_name: string;
  event_type: string;
  attendee_count: number;
  planned_start: string;
  planned_end: string;
  budget_estimate: string | number;
  event_priority: string;
  requirements: ParsedRequirement[];
}

export interface IntakePreviewResponse {
  draft: EventDraft;
  assumptions: string[];
  gaps: Array<{ field: string; message: string; severity: "critical" | "warning" }>;
  parser_mode: string;
  used_fallback: boolean;
}

export interface IntakeCommitResponse {
  event_id: string;
  client_id: string;
  location_id: string;
  requirement_ids: string[];
  parser_mode: string;
  used_fallback: boolean;
}

export interface GeneratedPlanAssignment {
  requirement_id: string;
  resource_type: string;
  resource_ids: string[];
  unassigned_count: number;
  estimated_cost: string | number;
}

export interface GeneratedPlanResponse {
  event_id: string;
  planner_run_id: string;
  recommendation_id: string;
  plan_id: string;
  solver: string;
  is_fully_assigned: boolean;
  assignments: GeneratedPlanAssignment[];
  estimated_cost: string | number;
}

export interface PlanCandidate {
  candidate_name: string;
  solver: string;
  estimated_cost: string | number;
  estimated_duration_minutes: string | number;
  predicted_delay_risk: string | number;
  coverage_ratio: string | number;
  plan_score: string | number;
  selection_explanation: string;
}

export interface RecommendBestPlanResponse {
  event_id: string;
  selected_candidate_name: string;
  selected_explanation: string;
  selected_plan: GeneratedPlanResponse;
  candidates: PlanCandidate[];
}

export interface RuntimeIncidentParseResponse {
  event_id: string;
  incident_id: string;
  incident_type: string;
  severity: string;
  description: string;
  root_cause?: string | null;
  reported_by?: string | null;
  cost_impact?: string | number | null;
  sla_impact: boolean;
  parser_mode: string;
  parse_confidence: number;
}

export interface ReplanResponse {
  event_id: string;
  incident_summary?: string | null;
  comparison: {
    new_cost: string | number;
    cost_delta?: string | number | null;
    decision_note: string;
    is_improved?: boolean | null;
  };
  generated_plan: GeneratedPlanResponse;
}

export interface PostEventParseResponse {
  event_id: string;
  parser_mode: string;
  parse_confidence: number;
  gaps: string[];
  draft_complete: Record<string, unknown>;
}
