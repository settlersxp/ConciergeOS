/**
 * API client for Prompt Group CRUD, execution, and scheduling.
 */

import type { ChainExecutionRequest, ChainExecutionResult, ChainStepRequest, ChainStepResult, PromptGroup, PromptGroupItemCreate, PromptGroupResult, PromptGroupScheduleCreate } from '../types/prompt';

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
export function createGroup(data: { name: string; description?: string | null; items?: PromptGroupItemCreate[]; is_chain_page?: boolean; page_route?: string | null }): Promise<PromptGroup> {
  return request<PromptGroup>('/api/prompt-groups', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/** Update a prompt group */
export function updateGroup(groupId: number, data: { name?: string | null; description?: string | null; is_active?: boolean | null; is_chain_page?: boolean | null; page_route?: string | null; items?: PromptGroupItemCreate[] | null }): Promise<PromptGroup> {
  return request<PromptGroup>(`/api/prompt-groups/${groupId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

/** Toggle a group's active state */
export function toggleGroup(groupId: number): Promise<PromptGroup> {
  return request<PromptGroup>(`/api/prompt-groups/${groupId}/toggle`, {
    method: 'PATCH',
  });
}

/** Delete a prompt group */
export function deleteGroup(groupId: number): Promise<{ ok: boolean; group_id: number }> {
  return request<{ ok: boolean; group_id: number }>(`/api/prompt-groups/${groupId}`, {
    method: 'DELETE',
  });
}

/** Toggle a single prompt group item's active state */
export function toggleItem(groupId: number, itemId: number): Promise<{ item_id: number; is_active: boolean }> {
  return request<{ item_id: number; is_active: boolean }>(`/api/prompt-groups/${groupId}/items/${itemId}/toggle`, {
    method: 'PATCH',
  });
}

/** Execute a prompt chain now */
export function executeGroup(groupId: number, initialInput?: string): Promise<Record<string, unknown>> {
  const query = initialInput ? `?initial_input=${encodeURIComponent(initialInput)}` : '';
  return request<Record<string, unknown>>(`/api/prompt-groups/${groupId}/execute${query}`, {
    method: 'POST',
  });
}

/**
 * Execute chain with user inputs (page mode).
 *
 * @param groupId The PromptGroup ID
 * @param inputs {step_position: {field: value}} for user-provided inputs
 * @param initialInput Optional initial text for the first step
 * @returns ChainExecutionResult with per-step details
 */
export function executeChain(
  groupId: number,
  inputs: Record<number, Record<string, string>>,
  initialInput?: string,
): Promise<ChainExecutionResult> {
  const body: ChainExecutionRequest = {
    inputs,
    initial_input: initialInput || "",
  };
  return request<ChainExecutionResult>(
    `/api/prompt-groups/${groupId}/execute-chain`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
}

/**
 * Execute a single chain step (page mode, step-by-step).
 *
 * @param groupId The PromptGroup ID
 * @param position The step position (1-based)
 * @param inputs User-provided inputs for this step
 * @param initialInput Optional initial text for the first step
 * @param accumulatedContext Context accumulated from previous steps
 * @param mediaFile Optional image/audio file for multimodal LLM input
 * @returns ChainStepResult with per-step details
 */
export function executeChainStep(
  groupId: number,
  position: number,
  inputs: Record<string, string>,
  initialInput?: string,
  accumulatedContext?: string,
  mediaFile?: File | null,
): Promise<ChainStepResult> {
  // When a file is attached, use FormData (multipart/form-data)
  if (mediaFile) {
    const formData = new FormData();
    formData.append("position", String(position));
    formData.append("initial_input", initialInput || "");
    formData.append("accumulated_context", accumulatedContext || "");
    formData.append("inputs_json", JSON.stringify(inputs));
    formData.append("file", mediaFile);

    const resp = fetch(`/api/prompt-groups/${groupId}/execute-chain-step`, {
      method: "POST",
      body: formData,
    });

    return resp.then(async (r) => {
      if (!r.ok) {
        const body = await r.text().catch(() => "");
        throw new Error(r.statusText + (body ? `: ${body}` : ""));
      }
      const text = await r.text();
      return text ? (JSON.parse(text) as ChainStepResult) : ({} as ChainStepResult);
    });
  }

  // No file — use plain JSON
  const body: ChainStepRequest = {
    position,
    inputs,
    initial_input: initialInput || "",
    accumulated_context: accumulatedContext || "",
  };
  return request<ChainStepResult>(
    `/api/prompt-groups/${groupId}/execute-chain-step`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
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

/** Cancel a specific schedule */
export function cancelSchedule(groupId: number, scheduleId: number): Promise<{ ok: boolean; schedule_id: number }> {
  return request<{ ok: boolean; schedule_id: number }>(`/api/prompt-groups/${groupId}/schedules/${scheduleId}`, {
    method: 'DELETE',
  });
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
  toggle: toggleGroup,
  remove: deleteGroup,
  execute: executeGroup,
  executeChain,
  executeChainStep,
  schedule: scheduleGroup,
  cancelSchedule,
  results: getResults,
  clearSchedules,
  toggleItem,
};
