import { useEffect, useState, useCallback } from "react";
import { useParams } from "react-router-dom";
import type { PromptGroup, PromptGroupItem, ChainStepResult } from "../types/prompt";
import { promptGroupsApi } from "../services/promptGroupsApi";
import { promptsApi } from "../services/promptsApi";
import ChainInputSection, { type InputField } from "../components/ui/ChainInputSection";
import ChainStepStatus from "../components/ui/ChainStepStatus";
import ChainOutputSection from "../components/ui/ChainOutputSection";

/**
 * Fetches the default prompt version for a step to get the user_prompt_template.
 */
async function fetchStepTemplate(item: PromptGroupItem): Promise<string | null> {
  try {
    const version = await promptsApi.getByVersion(item.prompt_id, item.prompt_version);
    return version?.user_prompt_template || null;
  } catch (err) {
    console.warn(`Failed to fetch template for ${item.prompt_id}:${item.prompt_version}`, err);
    return null;
  }
}

/**
 * Infer field names from a prompt template string.
 */
function inferInputFields(template: string): InputField[] {
  // Use the same logic from ChainInputSection
  const patterns: InputField[] = [];
  const regex = /\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g;
  let match: RegExpExecArray | null;
  const KNOWN_PLACEHOLDERS = new Set([
    "DATABASE_TABLES", "GUEST_INFORMATION", "ROOM_INFORMATION",
    "CURRENT_DATE", "AVAILABLE_TOOLS",
  ]);

  while ((match = regex.exec(template)) !== null) {
    const name = match[1];
    if (name.startsWith("step_")) continue;
    if (KNOWN_PLACEHOLDERS.has(name.toUpperCase())) continue;
    if (name.includes(".")) continue;
    const isDate = name.includes("date") || name.includes("time");
    const isSelect = name.includes("filter") || name.includes("status") || name.includes("type");
    patterns.push({
      name,
      label: name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
      type: isDate ? "date" : isSelect ? "select" : "text",
    });
  }
  return patterns;
}

interface StepDefinition {
  item: PromptGroupItem;
  template: string | null;
  inputFields: InputField[];
}

export default function PromptChainPage() {
  const { route } = useParams<{ route: string }>();
  const [group, setGroup] = useState<PromptGroup | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [stepDefinitions, setStepDefinitions] = useState<StepDefinition[]>([]);
  // Per-step accumulated context (each step's LLM output)
  const [stepOutputs, setStepOutputs] = useState<ChainStepResult[]>([]);
  // Per-step input values: { field_name: value } for each step
  const [stepInputs, setStepInputs] = useState<Record<number, Record<string, string>>>({});
  const [executing, setExecuting] = useState(false);

  useEffect(() => {
    const loadChainPage = async () => {
      try {
        const groups = await promptGroupsApi.list();
        const page = groups.find((g) => g.page_route === route);
        if (!page) {
          setGroup(null);
          return;
        }
        setGroup(page);

        // Fetch template for each step
        const definitions: StepDefinition[] = [];
        for (const item of page.items) {
          const template = await fetchStepTemplate(item);
          const fields = template ? inferInputFields(template) : [];
          definitions.push({ item, template, inputFields: fields });
        }
        setStepDefinitions(definitions);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load chain page");
      } finally {
        setLoading(false);
      }
    };
    loadChainPage();
  }, [route]);

  const handleInputChange = useCallback((stepPosition: number, name: string, value: string) => {
    setStepInputs((prev) => ({
      ...prev,
      [stepPosition]: { ...(prev[stepPosition] || {}), [name]: value },
    }));
  }, []);

  const runStep = useCallback(async (stepIndex: number) => {
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

      // If this is not the last step, show the next step's inputs
      if (stepIndex < stepDefinitions.length - 1) {
        // Auto-scroll to next step
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
  }, [group, stepDefinitions, stepOutputs, stepInputs]);

  const handleRun = useCallback((inputs: Record<number, Record<string, string>>, _initialInput?: string) => {
    // When the "Search" button is clicked on step 1, start executing from step 0
    setStepInputs(inputs);
    runStep(0);
  }, [runStep]);

  const handleRerun = useCallback(() => {
    // Clear all outputs and start over
    setStepOutputs([]);
    runStep(0);
  }, [runStep]);

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

  if (error) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-8">
        <div className="bg-red-50 border border-red-200 rounded-lg p-6">
          <h1 className="text-xl font-semibold text-red-800">Error</h1>
          <p className="text-red-700 mt-2">{error}</p>
        </div>
      </div>
    );
  }

  // Execute the last step if there are outputs and not all steps are done
  const allStepsDone = stepOutputs.length === stepDefinitions.length;
  const hasAnyOutputs = stepOutputs.length > 0;

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 space-y-6">
      {/* Header */}
      <div className="border-b border-gray-200 pb-4">
        <h1 className="text-3xl font-bold text-gray-900">{group.name}</h1>
        {group.description && (
          <p className="mt-1 text-gray-600">{group.description}</p>
        )}
        {hasAnyOutputs && (
          <div className="mt-3 flex items-center gap-3">
            <span className="text-sm text-gray-500">
              {stepOutputs.length} of {stepDefinitions.length} steps completed
            </span>
            {!allStepsDone && (
              <button
                onClick={handleRerun}
                className="text-sm text-indigo-600 hover:text-indigo-800 font-medium"
              >
                Start Over
              </button>
            )}
          </div>
        )}
      </div>

      {/* Chain Steps */}
      {stepDefinitions.map((def, index) => {
        const isInputStep = def.item.is_input_step || index === 0;
        const existingOutput = stepOutputs.find((o) => o.position === def.item.position);
        const isFirstStep = index === 0;
        const isStepDone = !!existingOutput;
        const isFailed = existingOutput?.status === "failed";

        return (
          <div key={def.item.item_id} id={`step-${index}`} className="space-y-4">
            {/* Step Header */}
            <div className="flex items-center gap-2">
              <span className={`inline-flex items-center justify-center w-8 h-8 rounded-full text-sm font-bold ${
                isFailed ? "bg-red-100 text-red-700" :
                isStepDone ? "bg-green-100 text-green-700" :
                "bg-gray-100 text-gray-600"
              }`}>
                {def.item.position}
              </span>
              <h2 className="text-lg font-semibold text-gray-900">
                Step {def.item.position}: {def.item.alias || def.item.prompt_id}
              </h2>
            </div>

            {isInputStep && !isStepDone && (
              /* Input Section */
              <ChainInputSection
                step={def.item}
                template={def.template || ""}
                inputs={stepInputs[def.item.position] || {}}
                onInputChange={(name, value) => handleInputChange(def.item.position, name, value)}
                onRun={isFirstStep ? handleRun : () => runStep(index)}
                loading={executing}
              />
            )}

            {isStepDone && (
              /* Output Section */
              isFailed ? (
                <ChainStepStatus step={existingOutput} />
              ) : index === stepDefinitions.length - 1 ? (
                /* Last step: show as final output */
                <ChainOutputSection
                  step={existingOutput}
                  output={existingOutput.response}
                  onRerun={handleRerun}
                />
              ) : (
                /* Intermediate step: show as step status */
                <ChainStepStatus step={existingOutput} />
              )
            )}

            {/* Show next step's input if current step is done and there are more steps */}
            {isStepDone && index < stepDefinitions.length - 1 && !stepDefinitions[index + 1].item.is_input_step && (
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <p className="text-sm text-blue-700">
                  Click below to execute the next step.
                </p>
                <button
                  onClick={() => runStep(index + 1)}
                  disabled={executing}
                  className="mt-2 px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
                >
                  {executing ? "Running..." : "Execute Next Step"}
                </button>
              </div>
            )}
          </div>
        );
      })}

      {/* All steps completed */}
      {allStepsDone && hasAnyOutputs && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-6 text-center">
          <p className="text-green-800 font-medium">All steps completed successfully!</p>
          <button
            onClick={handleRerun}
            className="mt-3 px-4 py-2 bg-green-600 text-white rounded-md text-sm font-medium hover:bg-green-700"
          >
            Start Over
          </button>
        </div>
      )}
    </div>
  );
}