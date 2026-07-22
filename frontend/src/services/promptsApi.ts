/**
 * API client for prompt version CRUD operations.
 */

import { request } from './api';
import type {
  CreatePromptRequest,
  DuplicatePromptRequest,
  PromptSummary,
  PromptVersion,
  UpdatePromptRequest,
} from '../types/prompt';

/**
 * Fetch summary of all prompt IDs.
 */
export function listAllPrompts(): Promise<PromptSummary[]> {
  return request<PromptSummary[]>('/api/prompts');
}

/**
 * List all versions for a prompt ID.
 */
export function listVersions(promptId: string): Promise<PromptVersion[]> {
  return request<PromptVersion[]>(`/api/prompts/${encodeURIComponent(promptId)}`);
}

/**
 * Get the default version for a prompt ID.
 */
export function getDefault(promptId: string): Promise<PromptVersion> {
  return request<PromptVersion>(`/api/prompts/${encodeURIComponent(promptId)}/default`);
}

/**
 * Get a specific version.
 */
export function getByVersion(promptId: string, version: number): Promise<PromptVersion> {
  return request<PromptVersion>(`/api/prompts/${encodeURIComponent(promptId)}/${version}`);
}

/**
 * Get a specific version by prompt ID and version number (alias for getByVersion).
 */
export function getPrompt(promptId: string, version: number): Promise<PromptVersion> {
  return getByVersion(promptId, version);
}

/**
 * Create a new prompt version.
 */
export function create(
  promptId: string,
  data: CreatePromptRequest,
): Promise<PromptVersion> {
  return request<PromptVersion>(`/api/prompts/${encodeURIComponent(promptId)}`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/**
 * Update an existing prompt version.
 */
export function update(
  promptId: string,
  version: number,
  data: UpdatePromptRequest,
): Promise<PromptVersion> {
  return request<PromptVersion>(`/api/prompts/${encodeURIComponent(promptId)}/${version}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

/**
 * Delete a prompt version.
 */
export function remove(promptId: string, version: number): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>(`/api/prompts/${encodeURIComponent(promptId)}/${version}`, {
    method: 'DELETE',
  });
}

/**
 * Duplicate a prompt version (creates next version).
 */
export function duplicate(
  promptId: string,
  version: number,
  data?: DuplicatePromptRequest,
): Promise<PromptVersion> {
  return request<PromptVersion>(
    `/api/prompts/${encodeURIComponent(promptId)}/${version}/duplicate`,
    {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    },
  );
}

/**
 * Set a version as the default.
 */
export function setDefault(promptId: string, version: number): Promise<PromptVersion> {
  return request<PromptVersion>(
    `/api/prompts/${encodeURIComponent(promptId)}/${version}/set-default`,
    {
      method: 'PATCH',
    },
  );
}

/**
 * AI-improve a prompt section via chat conversation.
 */
export function aiImprove(
  section: string,
  currentText: string,
  conversation: Array<{ role: string; content: string }>,
  model?: string,
): Promise<{ improved_text: string; summary?: string }> {
  return request<{ improved_text: string; summary?: string }>('/api/prompts/ai-improve', {
    method: 'POST',
    body: JSON.stringify({ section, current_text: currentText, conversation, model }),
  });
}

/** Re-exported as promptsApi object for consistency with existing api.ts pattern */
export const promptsApi = {
  listAll: listAllPrompts,
  listVersions,
  getDefault,
  getByVersion,
  create,
  update,
  remove,
  duplicate,
  setDefault,
  aiImprove,
};
/**
 * Fetch all available placeholders.
 */
export function listPlaceholders(): Promise<import('../types/placeholder').PlaceholderDefinition[]> {
  return request<import('../types/placeholder').PlaceholderDefinition[]>('/api/prompts/placeholders');
}

/**
 * Preview a prompt with resolved placeholders.
 */
export function previewPrompt(
  promptId: string,
  version: number,
): Promise<{ resolved_system_prompt: string; resolved_user_template: string }> {
  return request<{ resolved_system_prompt: string; resolved_user_template: string }>(
    `/api/prompts/${encodeURIComponent(promptId)}/${version}/preview`,
    { method: 'POST' },
  );
}

/**
 * Fetch the database field schema for runtime variable discovery.
 */
export function getFieldSchema(): Promise<Record<string, Array<{
  field: string;
  type: string;
  constraints: string[];
  nullable: boolean;
  primary_key: boolean;
  foreign_keys: string[];
}>>> {
  return request<Record<string, Array<{
    field: string;
    type: string;
    constraints: string[];
    nullable: boolean;
    primary_key: boolean;
    foreign_keys: string[];
  }>>>('/api/prompts/field-schema');
}
