/** Response types mirroring the FastAPI contract. */

export type ReviewStatus =
  | "pending"
  | "confirmed"
  | "rejected_false_positive"
  | "needs_more_information";

export type JobStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";

export type WorkOrderStatus =
  | "draft"
  | "pending"
  | "assigned"
  | "in_progress"
  | "completed_pending_verification"
  | "verified"
  | "reopened"
  | "rejected"
  | "cancelled";

export interface Pagination {
  limit: number;
  offset: number;
  total: number;
  has_more: boolean;
}

export interface Meta {
  request_id: string | null;
  pagination: Pagination | null;
}

export interface Envelope<T> {
  data: T;
  meta: Meta;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  organization_type: string;
  city: string | null;
  state: string | null;
  is_demo: boolean;
}

export interface CurrentUser {
  id: string;
  full_name: string;
  email: string;
  role: string;
  department_id: string | null;
  permissions: string[];
  organization: Organization;
  csrf_token: string | null;
}

export interface Session {
  user: CurrentUser;
  expires_in: number;
}

export interface Location {
  latitude: number;
  longitude: number;
  quality: string;
}

export interface Camera {
  id: string;
  camera_code: string;
  name: string;
  description: string | null;
  source_type: string;
  location: Location | null;
  connection_status: string;
  is_enabled: boolean;
  is_demo: boolean;
  has_secret_reference: boolean;
  last_seen_at: string | null;
  created_at: string;
}

export interface Video {
  id: string;
  camera_id: string | null;
  original_filename: string;
  content_type: string;
  file_size_bytes: number;
  checksum_sha256: string | null;
  source_type: string;
  status: string;
  recorded_at: string | null;
  duration_seconds: number | null;
  width: number | null;
  height: number | null;
  frame_rate: number | null;
  validation_error: string | null;
  uploaded_by: string;
  created_at: string;
  is_demo: boolean;
}

export interface Job {
  id: string;
  video_id: string;
  status: JobStatus;
  stage: string;
  progress: number;
  attempts: number;
  model_name: string | null;
  model_version: string | null;
  event_rules_version: string | null;
  result_summary: Record<string, unknown>;
  error_code: string | null;
  error_message_safe: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  can_retry: boolean;
}

export interface Evidence {
  id: string;
  evidence_type: string;
  label: string | null;
  content_type: string;
  original_filename: string | null;
  file_size_bytes: number;
  checksum_sha256: string;
  timestamp_in_video: number | null;
  incident_id: string | null;
  investigation_id: string | null;
  work_order_id: string | null;
  created_at: string;
  is_demo: boolean;
}

export interface Incident {
  id: string;
  incident_type: string;
  source_kind: string;
  severity: string | null;
  model_score: number | null;
  event_time: string;
  start_offset_seconds: number | null;
  end_offset_seconds: number | null;
  location: Location | null;
  description: string;
  review_status: ReviewStatus;
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_notes: string | null;
  camera_id: string | null;
  camera_code: string | null;
  video_id: string | null;
  ai_job_id: string | null;
  model_name: string | null;
  model_version: string | null;
  rule_name: string | null;
  rule_version: string | null;
  track_ids: number[];
  features: Record<string, unknown>;
  reason_codes: string[];
  limitations: string[];
  is_demo: boolean;
  created_at: string;
}

export interface IncidentAnalytics {
  window_from: string | null;
  window_to: string | null;
  total: number;
  by_review_status: Record<string, number>;
  by_type: Record<string, number>;
  by_source_kind: Record<string, number>;
  confirmed_observations: number;
  pending_candidates: number;
  historical_accidents_in_window: number;
  data_note: string;
}

export interface Department {
  id: string;
  name: string;
  department_type: string;
  contact_email: string | null;
  description: string | null;
  source_reference: string | null;
  is_demo: boolean;
  created_at: string;
}

export interface Contractor {
  id: string;
  name: string;
  registration_number: string;
  contact_email: string | null;
  contact_phone: string | null;
  source_reference: string | null;
  is_demo: boolean;
  created_at: string;
}

export interface Asset {
  id: string;
  asset_code: string;
  name: string;
  asset_type: string;
  address: string | null;
  department_id: string | null;
  location: Location | null;
  condition_status: string;
  source_reference: string | null;
  last_inspected_at: string | null;
  is_demo: boolean;
  created_at: string;
}

export interface Contract {
  id: string;
  contract_number: string;
  contract_type: string;
  contractor_id: string;
  contractor_name: string | null;
  department_id: string;
  department_name: string | null;
  scope_description: string;
  start_date: string;
  end_date: string;
  warranty_end_date: string | null;
  asset_ids: string[];
  source_reference: string | null;
  is_demo: boolean;
}

export interface ContractMatch {
  contract_id: string;
  contract_number: string;
  contract_type: string;
  contractor_id: string;
  contractor_name: string;
  scope_description: string;
  start_date: string;
  end_date: string;
  is_active_on_event_date: boolean;
  date_note: string;
  scope_notes: string | null;
  source_reference: string | null;
}

export interface Responsibility {
  status: string;
  asset_id: string | null;
  asset_code: string | null;
  asset_name: string | null;
  match_method: string;
  distance_meters: number | null;
  owning_department_id: string | null;
  owning_department_name: string | null;
  contracts: ContractMatch[];
  missing_records: string[];
  conflicts: string[];
  source_references: string[];
  verification_required: boolean;
  disclaimer: string;
}

export interface NearbyAsset {
  asset_id: string;
  asset_code: string;
  name: string;
  asset_type: string;
  distance_meters: number;
  department_id: string | null;
  location: Location | null;
}

export interface Recommendation {
  id: string;
  investigation_id: string;
  recommendation_text: string;
  rationale: string;
  priority: string;
  status: string;
  model_name: string | null;
  model_version: string | null;
  limitations: string[];
  created_by: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_notes: string | null;
  created_at: string;
  is_demo: boolean;
}

export interface Investigation {
  id: string;
  case_number: string;
  title: string;
  summary: string | null;
  incident_id: string | null;
  asset_id: string | null;
  assigned_department_id: string | null;
  assigned_to: string | null;
  status: string;
  responsibility_status: string | null;
  observed_facts: string[];
  hypotheses: Hypothesis[];
  missing_information: string[];
  analysis_source: string | null;
  analysis_model: string | null;
  analysis_generated_at: string | null;
  opened_by: string;
  closed_at: string | null;
  created_at: string;
  updated_at: string;
  is_demo: boolean;
}

export interface Hypothesis {
  hypothesis: string;
  supporting_record_ids: string[];
  counter_evidence: string[];
  confidence_label: string;
}

export interface InvestigationDetail {
  investigation: Investigation;
  incident: Incident | null;
  incident_evidence: Evidence[];
  asset: Asset | null;
  nearby_assets: NearbyAsset[];
  responsibility: Responsibility | null;
  recommendations: Recommendation[];
  work_orders: WorkOrder[];
  evidence: Evidence[];
  source_records: string[];
  disclaimer: string;
}

export interface WorkOrder {
  id: string;
  work_order_number: string;
  investigation_id: string;
  recommendation_id: string | null;
  assigned_department_id: string;
  department_name: string | null;
  assigned_to: string | null;
  title: string;
  description: string;
  status: WorkOrderStatus;
  priority: string;
  due_date: string | null;
  completed_at: string | null;
  completion_notes: string | null;
  completed_by: string | null;
  verified_at: string | null;
  verified_by: string | null;
  created_at: string;
  updated_at: string;
  is_demo: boolean;
  allowed_transitions: WorkOrderStatus[];
}

export interface StatusHistory {
  id: string;
  from_status: string | null;
  to_status: string;
  changed_by: string;
  note: string | null;
  created_at: string;
}

export interface Verification {
  id: string;
  verified_by: string;
  verification_status: string;
  notes: string;
  verified_at: string;
  created_at: string;
}

export interface WorkOrderDetail extends WorkOrder {
  history: StatusHistory[];
  verifications: Verification[];
  evidence: Evidence[];
  separation_of_duties: boolean;
  can_submit_completion: boolean;
  can_verify: boolean;
}

export interface AuditEntry {
  id: string;
  actor_id: string | null;
  actor_label: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  request_id: string | null;
  summary: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface AccidentRecord {
  id: string;
  external_reference: string | null;
  location: Location | null;
  accident_time: string | null;
  accident_date: string | null;
  accident_type: string | null;
  severity: string | null;
  road_name: string | null;
  source_name: string;
  source_reference: string;
  verification_status: string;
  import_batch_id: string | null;
  is_demo: boolean;
}

export interface HotspotCluster {
  cluster_key: string;
  latitude: number;
  longitude: number;
  radius_meters: number;
  counts: Record<string, number>;
  total_records: number;
  source_mix: string[];
  categories: Record<string, number>;
  first_seen: string | null;
  last_seen: string | null;
  record_ids: string[];
  label: string;
}

export interface HotspotAnalysis {
  id: string;
  method: string;
  radius_meters: number;
  min_size: number;
  window_from: string | null;
  window_to: string | null;
  generated_at: string;
  methodology_note: string;
  data_sources: string[];
  clusters: HotspotCluster[];
  unlocated_count: number;
  is_demo: boolean;
}

export interface BootstrapMeta {
  environment: string;
  demo_mode: boolean;
  permissions: string[];
  roles: string[];
  max_upload_bytes: number;
  max_video_duration_seconds: number;
  supported_content_types: string[];
  live_cctv_enabled: boolean;
  llm_enabled: boolean;
  detector_backend: string;
}

export interface AdminUser {
  id: string;
  full_name: string;
  email: string;
  role: string;
  department_id: string | null;
  is_active: boolean;
  last_login_at: string | null;
  created_at: string;
  is_demo: boolean;
}

export interface UploadSession {
  video_id: string;
  upload_url: string;
  upload_method: string;
  expires_at: string;
  max_bytes: number;
}

export interface InvestigationAnalysis {
  investigation_id: string;
  analysis_source: string;
  model_name: string | null;
  generated_at: string;
  observed_facts: string[];
  potential_root_causes: Hypothesis[];
  missing_information: string[];
  potentially_relevant_authorities: string[];
  recommended_actions: Array<{
    action: string;
    rationale: string;
    priority: string;
    requires_human_approval: boolean;
    category?: string;
  }>;
  limitations: string[];
  human_verification_required: boolean;
}
