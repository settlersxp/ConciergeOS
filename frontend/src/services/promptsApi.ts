/**
 * API client for prompt version CRUD operations.
 */

import type {
  CreatePromptRequest,
  DuplicatePromptRequest,
  PromptSummary,
  PromptVersion,
  UpdatePromptRequest,
} from '../types/prompt';

/** Generic fetch helper that parses JSON responses */
async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!resp.ok) {
    const body = await resp.text().catch(() => '');
    throw new Error(resp.statusText + (body ? `: ${body}` : ''));
  }
  const text = await resp.text();
  return text ? (JSON.parse(text) as T) : ({} as T);
}

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
};