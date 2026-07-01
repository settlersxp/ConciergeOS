import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import type { PromptGroup, ChainExecutionResult, ChainStepResult } from "../types/prompt";
import type { PromptVersion } from "../types/prompt";
import { promptGroupsApi } from "../services/promptGroupsApi";
import { promptsApi } from "../services/promptsApi";
import ChainInputSection from "../components/ui/ChainInputSection";
import ChainStepStatus from "../components/ui/ChainStepStatus";
import ChainOutputSection from "../components/ui/ChainOutputSection";

/**
 * Fetches the default prompt version for each step to get the user_prompt_template.
 */
async function fetchStepTemplates(
  items: Array<{ prompt_id: string; prompt_version: number }>,
): Promise<Map<string, string>> {
  const templates = new Map<string, string>();
  for (const item of items) {
    try {
      const version = await promptsApi.getByVersion(item.prompt_id, item.prompt_version);
      if (version?.user_prompt_template) {
        templates.set(`${item.prompt_id}:${item.prompt_version}`, version.user_prompt_template);
      }
    } catch (err) {
      console.warn(`Failed to fetch template for ${item.prompt_id}:${item.prompt_version}`, err);
    }
  }
  return templates;
}

export default function PromptChainPage() {
  const { route } = useParams<{ route: string }>();
  const [group, setGroup] = useState<PromptGroup | null>(null);
  const [loading, setLoading] = useState(true);
  const [chainResult, setChainResult] = useState<ChainExecutionResult | null>(null);
  const [inputs, setInputs] = useState<Record<string, string>>({});
  const [stepTemplates, setStepTemplates] = useState<Map<string, string>>(new Map());

  useEffect(() => {
    const loadChainPage = async () => {
      try {
        const groups = await promptGroupsApi.list();
        const page = groups.find((g) => g.page_route === route);
        if (page) {
          setGroup(page);

          // Fetch default prompt templates for each step
          const templates = await fetchStepTemplates(page.items);
          setStepTemplates(templates);
        }
      } catch (err) {
        console.error("Failed to load chain page:", err);
      } finally {
        setLoading(false);
      }
    };
    loadChainPage();
  }, [route]);

  const handleInputChange = (name: string, value: string) => {
    setInputs((prev) => ({ ...prev, [name]: value }));
  };

  const handleRun = async (stepInputs: Record<number, Record<string, string>>) => {
    if (!group) return;
    try {
      setLoading(true);
      // Collect all input values from step 1 (the first input step)
      const firstStepInputs = stepInputs[1] || {};
      const initialInput = firstStepInputs.customer_name || inputs.customer_name || "";
      const result = await promptGroupsApi.executeChain(
        group.group_id,
        stepInputs,
        initialInput,
      );
      setChainResult(result);
    } catch (err) {
      console.error("Chain execution failed:", err);
      const errorMsg = err instanceof Error ? err.message : "Unknown error";
      const failedResult: ChainExecutionResult = {
        group_id: group.group_id,
        group_name: group.name,
        executed_at: new Date().toISOString(),
        scheduled: false,
        success: false,
        steps_count: 1,
        steps: [{
          position: 1,
          prompt_id: "user-input",
          prompt_version: 1,
          status: "failed",
          response: null,
          cached: false,
          error: errorMsg,
          user_message: null,
        }],
        final_output: null,
        result_file: "",
        result_id: 0,
      };
      setChainResult(failedResult);
    } finally {
      setLoading(false);
    }
  };

  const handleRerun = () => {
    if (!group) return;
    handleRun({ 1: inputs });
  };

  if (loading) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-8">
        <div className="flex items-center justify-center h-64">
          <div className="text-gray-500">Loading...</div>
        </div>
      </div>
    );
  }

  if (!group) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-8">
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6">
          <h1 className="text-xl font-semibold text-yellow-800 mb-2">
            Chain Page Not Found
          </h1>
          <p className="text-yellow-700">
            No chain page was found for route <code>/prompt-chains/{route}</code>.
          </p>
        </div>
      </div>
    );
  }

  const finalStep = chainResult?.steps[chainResult.steps.length - 1];
  const intermediateSteps = chainResult?.steps.slice(1, -1) || [];

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 space-y-6">
      {/* Header */}
      <div className="border-b border-gray-200 pb-4">
        <h1 className="text-3xl font-bold text-gray-900">{group.name}</h1>
        {group.description && (
          <p className="mt-1 text-gray-600">{group.description}</p>
        )}
      </div>

      {/* Input Section */}
      {group.items[0] && (
        <ChainInputSection
          step={group.items[0]}
          template={stepTemplates.get(`${group.items[0].prompt_id}:${group.items[0].prompt_version}`) || ""}
          inputs={inputs}
          onInputChange={handleInputChange}
          onRun={handleRun}
          loading={loading}
        />
      )}

      {/* Intermediate Steps */}
      {intermediateSteps.map((step) => (
        <ChainStepStatus key={step.position} step={step} />
      ))}

      {/* Final Output */}
      {finalStep && (
        <ChainOutputSection
          step={finalStep}
          output={chainResult?.final_output || null}
          onRerun={handleRerun}
        />
      )}
    </div>
  );
}