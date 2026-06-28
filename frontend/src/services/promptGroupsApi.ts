/**
 * API client for Prompt Group CRUD, execution, and scheduling.
 */

import type { PromptGroup, PromptGroupItemCreate, PromptGroupResult, PromptGroupScheduleCreate } from '../types/prompt';

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

/** List all prompt groups */
export function listGroups(): Promise<PromptGroup[]> {
  return request<PromptGroup[]>('/api/prompt-groups');
}

/** Get a single group by ID */
export function getGroup(groupId: number): Promise<PromptGroup> {
  return request<PromptGroup>(`/api/prompt-groups/${groupId}`);
}

/** Create a new prompt group */
export function createGroup(data: { name: string; description?: string | null; items?: PromptGroupItemCreate[] }): Promise<PromptGroup> {
  return request<PromptGroup>('/api/prompt-groups', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/** Update a prompt group */
export function updateGroup(groupId: number, data: { name?: string | null; description?: string | null; items?: PromptGroupItemCreate[] | null }): Promise<PromptGroup> {
  return request<PromptGroup>(`/api/prompt-groups/${groupId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

/** Delete a prompt group */
export function deleteGroup(groupId: number): Promise<{ ok: boolean; group_id: number }> {
  return request<{ ok: boolean; group_id: number }>(`/api/prompt-groups/${groupId}`, {
    method: 'DELETE',
  });
}

/** Execute a prompt chain now */
export function executeGroup(groupId: number, initialInput?: string): Promise<Record<string, unknown>> {
  const query = initialInput ? `?initial_input=${encodeURIComponent(initialInput)}` : '';
  return request<Record<string, unknown>>(`/api/prompt-groups/${groupId}/execute${query}`, {
    method: 'POST',
  });
}

/** Schedule a prompt chain execution */
export function scheduleGroup(groupId: number, data: PromptGroupScheduleCreate): Promise<{ ok: boolean; schedule_id: number; group_id: number; run_at: string; job_id: string }> {
  return request<{ ok: boolean; schedule_id: number; group_id: number; run_at: string; job_id: string }>(
    `/api/prompt-groups/${groupId}/schedule`,
    {
      method: 'POST',
      body: JSON.stringify(data),
    },
  );
}

/** Get execution history for a group */
export function getResults(groupId: number): Promise<PromptGroupResult[]> {
  return request<PromptGroupResult[]>(`/api/prompt-groups/${groupId}/results`);
}

/** Clear all active schedules for a group */
export function clearSchedules(groupId: number): Promise<{ ok: boolean; deleted: number }> {
  return request<{ ok: boolean; deleted: number }>(`/api/prompt-groups/${groupId}/schedules`, {
    method: 'DELETE',
  });
}

/** Convenience object */
export const promptGroupsApi = {
  list: listGroups,
  get: getGroup,
  create: createGroup,
  update: updateGroup,
  remove: deleteGroup,
  execute: executeGroup,
  schedule: scheduleGroup,
  results: getResults,
  clearSchedules,
};