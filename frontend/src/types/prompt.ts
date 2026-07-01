/** TypeScript interfaces for versioned prompts. */

export interface PromptVersion {
  id: number;
  prompt_id: string;
  version: number;
  name: string;
  intention: string;
  restrictions: string;
  output_structure: string;
  user_prompt_template: string;
  model_id: number | null;
  is_default: boolean;
  metadata: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface PromptSummary {
  prompt_id: string;
  default_version: number;
  version_count: number;
  name: string;
}

export interface CreatePromptRequest {
  name: string;
  intention: string;
  restrictions: string;
  output_structure: string;
  user_prompt_template: string;
  model_id?: number | null;
  metadata?: Record<string, unknown>;
}

export interface UpdatePromptRequest {
  name?: string;
  intention?: string;
  restrictions?: string;
  output_structure?: string;
  user_prompt_template?: string;
  model_id?: number | null;
  metadata?: Record<string, unknown>;
}

export interface DuplicatePromptRequest {
  name?: string;
}

// ---------------------------------------------------------------------------
// Prompt Group types
// ---------------------------------------------------------------------------

export interface PromptGroupItem {
  item_id: number;
  group_id: number;
  position: number;
  prompt_id: string;
  prompt_version: number;
  alias?: string;
  is_input_step?: boolean;
}

export interface PromptGroupItemCreate {
  position: number;
  prompt_id: string;
  prompt_version: number;
  alias?: string;
  is_input_step?: boolean;
}

export interface PromptGroupSchedule {
  schedule_id: number;
  group_id: number;
  run_at: string;
  schedule_type: string;
  active: boolean;
  created_at: string;
}

export interface PromptGroupScheduleCreate {
  run_at: string;
  schedule_type?: string;
}

export interface PromptGroupResult {
  result_id: number;
  group_id: number;
  executed_at: string;
  scheduled: boolean;
  result_file: string | null;
  status: string;
  error_message: string | null;
}

export interface PromptGroup {
  group_id: number;
  name: string;
  description: string | null;
  is_active: boolean;
  is_chain_page?: boolean;
  page_route?: string | null;
  created_at: string;
  updated_at: string;
  items: PromptGroupItem[];
  schedules: PromptGroupSchedule[];
  results: PromptGroupResult[];
}

// ---------------------------------------------------------------------------
// Chain page types
// ---------------------------------------------------------------------------

export interface ChainExecutionRequest {
  inputs: Record<number, Record<string, string>>;
  initial_input?: string;
}

export interface ChainStepResult {
  position: number;
  prompt_id: string;
  prompt_version: number;
  alias?: string;
  status: "running" | "success" | "failed";
  response: string | null;
  cached: boolean;
  error: string | null;
  user_message: string | null;
  system_prompt?: string | null;
  references?: string[];
}

export interface ChainExecutionResult {
  group_id: number;
  group_name: string;
  executed_at: string;
  scheduled: boolean;
  success: boolean;
  steps_count: number;
  steps: ChainStepResult[];
  final_output: string | null;
  result_file: string;
  result_id: number;
}
