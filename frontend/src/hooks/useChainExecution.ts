/**
 * Hook that manages chain step-by-step execution:
 * - Tracks per-step inputs and outputs
 * - Handles step execution with accumulated context
 * - Provides runStep, handleRun, handleRerun callbacks
 *
 * Extracted from PromptChainPage to separate execution logic from rendering.
 */

import { useState, useCallback } from "react";
import type { PromptGroup, PromptGroupItem, ChainStepResult } from "../types/prompt";
import { promptGroupsApi } from "../services/promptGroupsApi";

export interface StepDefinition {
  item: PromptGroupItem;
  template: string | null;
}

interface UseChainExecutionParams {
  group: PromptGroup | null;
  stepDefinitions: StepDefinition[];
}

interface UseChainExecutionReturn {
  stepInputs: Record<number, Record<string, string>>;
  stepOutputs: ChainStepResult[];
  executing: boolean;
  handleInputChange: (stepPosition: number, name: string, value: string) => void;
  runStep: (stepIndex: number) => Promise<void>;
  handleRun: (inputs: Record<number, Record<string, string>>, _initialInput?: string) => void;
  handleRerun: () => void;
  allStepsDone: boolean;
  hasAnyOutputs: boolean;
}

/**
 * Fetches the default prompt version for a step to get the user_prompt_template.
 */
async function fetchStepTemplate(item: PromptGroupItem): Promise<string | null> {
  try {
    const { promptsApi } = await import("../services/promptsApi");
    const version = await promptsApi.getByVersion(item.prompt_id, item.prompt_version);
    return version?.user_prompt_template || null;
  } catch (err) {
    console.warn(`Failed to fetch template for ${item.prompt_id}:${item.prompt_version}`, err);
    return null;
  }
}

export function useChainExecution({
  group,
  stepDefinitions,
}: UseChainExecutionParams): UseChainExecutionReturn {
  const [stepOutputs, setStepOutputs] = useState<ChainStepResult[]>([]);
  const [stepInputs, setStepInputs] = useState<Record<number, Record<string, string>>>({});
  const [executing, setExecuting] = useState(false);

  const handleInputChange = useCallback((stepPosition: number, name: string, value: string) => {
    setStepInputs((prev) => ({
      ...prev,
      [stepPosition]: { ...(prev[stepPosition] || {}), [name]: value },
    }));
  }, []);

  const runStep = useCallback(
    async (stepIndex: number) => {
      if (!group || stepIndex >= stepDefinitions.length) return;

      const def = stepDefinitions[stepIndex];
      const position = def.item.position;

      // Gather accumulated context: join all previous step outputs
      const previousOutputs = stepOutputs.slice(0, stepIndex);
      const accumulatedContext = previousOutputs
        .map((o) => o.response || `[Step ${o.position} failed: ${o.error || "unknown error"}]`)
        .join("\n\n");

      setExecuting(true);
      try {
        const result = await promptGroupsApi.executeChainStep(
          group.group_id,
          position,
          stepInputs[position] || {},
          position === 1 ? (stepInputs[1]?.customer_name || "") : undefined,
          accumulatedContext,
        );

        setStepOutputs((prev) => {
          const filtered = prev.filter((o) => o.position !== position);
          return [...filtered, result];
        });

        // Auto-scroll to next step
        if (stepIndex < stepDefinitions.length - 1) {
          const nextEl = document.getElementById(`step-${stepIndex + 1}`);
          nextEl?.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : "Unknown error";
        const failedResult: ChainStepResult = {
          position,
          prompt_id: def.item.prompt_id,
          prompt_version: def.item.prompt_version,
          status: "failed",
          response: null,
          cached: false,
          error: errorMsg,
          user_message: null,
          system_prompt: null,
        };
        setStepOutputs((prev) => {
          const filtered = prev.filter((o) => o.position !== position);
          return [...filtered, failedResult];
        });
      } finally {
        setExecuting(false);
      }
    },
    [group, stepDefinitions, stepOutputs, stepInputs],
  );

  const handleRun = useCallback(
    (inputs: Record<number, Record<string, string>>, _initialInput?: string) => {
      setStepInputs(inputs);
      runStep(0);
    },
    [runStep],
  );

  const handleRerun = useCallback(() => {
    setStepOutputs([]);
    runStep(0);
  }, [runStep]);

  const allStepsDone = stepOutputs.length === stepDefinitions.length && stepDefinitions.length > 0;
  const hasAnyOutputs = stepOutputs.length > 0;

  return {
    stepInputs,
    stepOutputs,
    executing,
    handleInputChange,
    runStep,
    handleRun,
    handleRerun,
    allStepsDone,
    hasAnyOutputs,
  };
}

/**
 * Helper: Build step definitions from a PromptGroup by fetching templates.
 */
export async function buildStepDefinitions(items: PromptGroupItem[]): Promise<StepDefinition[]> {
  const definitions: StepDefinition[] = [];
  for (const item of items) {
    const template = await fetchStepTemplate(item);
    definitions.push({ item, template });
  }
  return definitions;
}