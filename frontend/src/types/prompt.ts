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
  metadata?: Record<string, unknown>;
}

export interface UpdatePromptRequest {
  name?: string;
  intention?: string;
  restrictions?: string;
  output_structure?: string;
  user_prompt_template?: string;
  metadata?: Record<string, unknown>;
}

export interface DuplicatePromptRequest {
  name?: string;
}