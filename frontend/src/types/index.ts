/** Reservation & Summary types — mirror app/schemas.py Pydantic models */

export interface Reservation {
  reservation_id: number;
  room_id: number;
  room_name: string;
  guest_id: number;
  first_name: string;
  last_name: string;
  check_in_date: string;
  check_out_date: string;
  status: string;
  booking_source: string;
}

export interface ErrorResponse {
  reservation_id: number;
  room_name: string;
  room_id: number;
  guest_name: string;
  check_in_date: string;
  check_out_date: string;
  status: string;
  error_type: string;
  description: string;
}

export interface ReservationsSummary {
  rooms: Record<string, Reservation[]>;
  errors: ErrorResponse[];
}

/** Guest Search */

export interface GuestSearchRequest {
  customer_name: string;
  runtime_variables?: Record<string, string>;
}

export interface GuestSearchResponse {
  query: string;
  llm_response: string;
  cached?: boolean;
}

/** Settings — matches app/config.py TestSettings dataclass */

export interface TestSettings {
  models_endpoint: string;
  model_name: string;
  vllm_version: string;
  thinking_enabled: boolean;
  expected_format: string;
}

export interface AppSettings {
  test_settings: TestSettings;
}

export interface ModelsApiResponse {
  data: Array<{
    id: string;
    object?: string;
    vllm_version?: string;
    capabilities?: { thinking?: boolean };
    type?: string;
    extra?: { vllm_version?: string };
  }>;
}

/** Performance Testing */

export type TestMode = "single" | "multi";
export type DataFormat = "csv" | "json" | "xml" | "tool_calling";
export type BatchType = "sequential" | "concurrent";
export type StatusType = "running" | "success" | "error";

export interface PerformanceTestRequest {
  customer_name?: string;
  vllm_url?: string;
  models_endpoint?: string;
  sequential_batch_size?: number;
  concurrent_batch_size?: number;
  test_mode?: TestMode;
  friendly_name?: string;
  model_name?: string;
  vllm_version?: string;
  thinking_enabled?: boolean;
  user_prompt?: string;
  expected_response_format?: string;
  data_format?: DataFormat;
  batch_uuid?: string;
  prompt_id?: string;
  prompt_version?: number;
  runtime_variables?: Record<string, string>;
}

export interface TestResult {
  id: number;
  run_id: string;
  batch_uuid?: string;
  friendly_name?: string;
  batch_type: BatchType;
  request_index: number;
  model_name: string;
  context_length: number;
  vllm_version: string;
  thinking_enabled: boolean;
  system_prompt: string;
  user_prompt: string;
  response_format: string;
  json_malformed: boolean | null;
  response_length: number | null;
  request_sent_time: string;
  response_received_time: string;
  response_content: string;
  valid_response: boolean | null;
  identifier?: string | null;
  customer_name?: string;
}

export interface RunTestResponse {
  run_id: number;
  batch_uuid: string;
  friendly_name?: string;
  model_name?: string;
  vllm_version?: string;
  thinking_enabled?: boolean;
  total_requests: number;
  sequential_results: Array<{
    batch_type: BatchType;
    context_length: number;
    response_format: string;
    json_malformed: boolean | null;
    response_length: number | null;
    request_sent_time: string;
    response_received_time: string;
    elapsed: number;
  }>;
  concurrent_results: Array<{
    batch_type: BatchType;
    context_length: number;
    response_format: string;
    json_malformed: boolean | null;
    response_length: number | null;
    request_sent_time: string;
    response_received_time: string;
    elapsed: number;
  }>;
}

export interface Batch {
  batch_uuid: string;
  friendly_name: string;
  total_requests: number;
  first_run_time: string;
}

export interface PerformanceStats {
  batch_uuid: string;
  friendly_name: string;
  model_name: string;
  batch_type: "sequential" | "concurrent";
  avg_speed_seconds: number;
  accuracy_pct: number;
  total_requests: number;
}

export interface TestGuest {
  guest_id: number;
  first_name: string;
  last_name: string;
  full_name: string;
  reservation_count: number;
}

export interface ReservationDetail {
  reservation_id: number;
  room_id: number;
  room_name: string;
  check_in_date: string;
  check_out_date: string;
  status: string;
  booking_source: string;
  created_at: string | null;
}

export interface GuestDetail {
  guest_id: number;
  first_name: string;
  last_name: string;
  date_of_birth: string | null;
  is_special_guest: boolean | null;
  special_preferences: string | null;
  reservations: ReservationDetail[];
}

export interface GenerateAllResponse {
  ok: boolean;
  error?: string;
  files: {
    csv: { path: string; size_bytes: number };
    json: { path: string; size_bytes: number };
    xml: { path: string; size_bytes: number };
  };
}

export interface SetupGuestsResponse {
  ok: boolean;
  error?: string;
  total: number;
  guests: TestGuest[];
}

export interface SummaryData {
  total: number;
  avg: string;
  min: string;
  max: string;
  model?: string;
}

export interface DiffResult {
  left: string;
  right: string;
}

export interface DiffOp {
  type: "common" | "added" | "removed";
  line: string;
}

/** Shift Reservation */

export interface ShiftRequest {
  days?: number;
}

export interface ShiftSampleEntry {
  check_in: string;
  check_out: string;
}

export interface ShiftResponse {
  ok: boolean;
  shifted?: number;
  days?: number;
  message?: string;
  error?: string;
  before?: ShiftSampleEntry[];
  after?: ShiftSampleEntry[];
}

/** Models API */

export interface VLLMModel {
  id: string;
  object: string;
}

/** Validation */

export interface SingleGuestValidation {
  guest_id: number;
  guest_name: string;
  result_id: number | null;
  is_match: boolean | null;
  /** Human's previous validation flag from the database (null = not reviewed) */
  valid_response: boolean | null;
  llm_reasoning: string | null;
  ground_truth: string | null;
  llm_response_content: string | null;
}

export interface ValidateGuestsResponse {
  ok: boolean;
  error?: string;
  results: SingleGuestValidation[];
  summary?: {
    total_guests: number;
    matched: number;
    total_validated: number;
    accuracy: number;
  };
}

/** Field Schema (runtime variable discovery) */

export interface FieldInfo {
  field: string;
  type: string;
  constraints: string[];
  nullable: boolean;
  primary_key: boolean;
  foreign_keys: string[];
}

export interface FieldSchema {
  [tableName: string]: FieldInfo[];
}

/** Prompt Performance Analysis */

export interface PromptOverview {
  prompt_id: string;
  prompt_version: number | null;
  prompt_name: string;
  model_name: string;
  batch_type: "sequential" | "concurrent";
  avg_speed_seconds: number;
  accuracy_pct: number;
  total_runs: number;
  total_requests: number;
}

export interface PromptDetailRun {
  batch_uuid: string;
  friendly_name: string;
  batch_type: "sequential" | "concurrent";
  model_name: string;
  vllm_version: string;
  thinking_enabled: boolean;
  request_sent_time: string;
  response_received_time: string;
  elapsed: number;
  valid_response: boolean | null;
  response_length: number | null;
  json_malformed: boolean | null;
  request_index: number;
}

export interface PromptDetailResponse {
  prompt_id: string;
  prompt_version: number | null;
  prompt_name: string;
  model_name: string | null;
  batch_type: string | null;
  avg_speed_seconds: number;
  accuracy_pct: number;
  total_runs: number;
  total_requests: number;
  runs: PromptDetailRun[];
}

export interface PromptBatchInfo {
  batch_uuid: string;
  batch_type: string;
  model_name: string;
  vllm_version: string | null;
  thinking_enabled: boolean | null;
  friendly_name: string | null;
  avg_speed_seconds: number;
  accuracy_pct: number;
  total_requests: number;
  min_speed_seconds: number;
  max_speed_seconds: number;
  individual_timings: number[];
}

export interface PromptBatchStatsResponse {
  prompt_id: string;
  prompt_version: number | null;
  prompt_name: string;
  batches: PromptBatchInfo[];
  overall_avg_speed: number;
  overall_accuracy: number;
  total_batches: number;
  total_requests: number;
}

/** Grouped batch data for the reorganized Batch Details table */
export interface GroupedBatchTypeStats {
  concurrent?: BatchTypeRow;
  sequential?: BatchTypeRow;
  // Computed overall metrics (average of concurrent and sequential)
  overall_avg_speed?: number;
  overall_accuracy?: number;
  overall_total_requests?: number;
  overall_min_speed?: number;
  overall_max_speed?: number;
}

export interface BatchTypeRow {
  avg_speed_seconds: number;
  min_speed_seconds: number;
  max_speed_seconds: number;
  accuracy_pct: number;
  total_requests: number;
}

export interface GroupedBatch {
  batch_name: string;
  batch_uuids: string[];
  model_name: string;
  types: GroupedBatchTypeStats;
}
