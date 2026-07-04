import { useEffect, useState } from "react";
import { PageHeader, Card, Button, ChainInputSection, ChainStepStatus, ChainOutputSection } from "../components/ui";
import { useChainPageData } from "../hooks/useChainPageData";
import { useChainExecution } from "../hooks/useChainExecution";

/**
 * PromptChainPage renders a prompt group as a full page.
 *
 * Uses:
 * - useChainPageData() for data loading (group resolution, step definitions)
 * - useChainExecution() for step-by-step chain execution logic
 * - Shared ChainInputSection, ChainStepStatus, ChainOutputSection components
 *
 * This component is now a thin presenter (~120 lines) since all business
 * logic is extracted into custom hooks.
 */
export default function PromptChainPage() {
  // Data loading (group resolution + step definitions with templates)
  const { group, loading, error, stepDefinitions } = useChainPageData();

  // Chain execution logic (step inputs/outputs, runStep, etc.)
  const execution = useChainExecution({ group, stepDefinitions });

  // Track which step is currently executing (for UI feedback)
  const [executingStep, setExecutingStep] = useState<number | null>(null);

  // Scroll to top when chain completes
  useEffect(() => {
    if (execution.allStepsDone) {
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  }, [execution.allStepsDone]);

  // ── Loading / Error / NotFound States ────────────────────────────

  if (loading) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-8">
        <PageHeader title="Loading..." description="Finding your chain page." />
        <Card><div className="py-8 text-center text-primary-500">⏳ Loading chain page...</div></Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-8">
        <PageHeader title="Error" description="Something went wrong." />
        <Card>
          <div className="py-8 text-center text-accent-600">
            <p className="text-lg font-medium">Failed to load chain page</p>
            <p className="mt-2 text-sm">{error}</p>
          </div>
        </Card>
      </div>
    );
  }

  if (!group) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-8">
        <PageHeader title="Page Not Found" description="The requested chain page does not exist." />
        <Card>
          <div className="py-8 text-center text-primary-500">
            <p className="text-lg font-medium">Chain page not found</p>
            <p className="mt-2 text-sm">This prompt group is not configured as a chain page.</p>
          </div>
        </Card>
      </div>
    );
  }

  // ── Render Chain Page ─────────────────────────────────────────────

  const handleStepInputChange = (stepIndex: number) => (name: string, value: string) => {
    execution.handleInputChange(stepDefinitions[stepIndex].item.position, name, value);
  };

  // Wrap runStep to track which step is executing
  const runStepWithTracking = async (stepIndex: number, mediaFile?: File | null) => {
    setExecutingStep(stepIndex);
    try {
      await execution.runStep(stepIndex, mediaFile);
    } finally {
      setExecutingStep(null);
    }
  };

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      {/* Page Header */}
      <PageHeader title={group.name} description={group.description || ""} />

      {/* Completion Banner */}
      {execution.allStepsDone && (
        <Card className="mb-6 border-l-4 border-l-green-500 bg-green-50 dark:bg-green-900/20">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-green-900 dark:text-green-200">
                All {stepDefinitions.length} steps completed
              </p>
              <p className="text-sm text-green-700 dark:text-green-300">
                Chain execution finished successfully.
              </p>
            </div>
            <Button variant="primary" onClick={execution.handleRerun}>
              Start Over
            </Button>
          </div>
        </Card>
      )}

      {/* Progress Indicator */}
      {execution.hasAnyOutputs && !execution.allStepsDone && (
        <Card className="mb-6">
          <div className="flex items-center gap-3">
            <div className="flex-1 bg-surface-200 dark:bg-primary-700 rounded-full h-2.5">
              <div
                className="bg-secondary-500 h-2.5 rounded-full transition-all duration-300"
                style={{ width: `${(execution.stepOutputs.length / stepDefinitions.length) * 100}%` }}
              />
            </div>
            <span className="text-sm font-medium text-primary-600 dark:text-primary-400">
              {execution.stepOutputs.length} of {stepDefinitions.length} steps
            </span>
          </div>
        </Card>
      )}

      {/* Render Each Step */}
      {stepDefinitions.map((def, index) => {
        const position = def.item.position;
        const isInputStep = def.item.is_input_step;
        const stepOutput = execution.stepOutputs.find((o) => o.position === position);
        const isLastStep = index === stepDefinitions.length - 1;
        const isNextExecutable =
          !execution.executing &&
          index === execution.stepOutputs.length &&
          !stepOutput;

        return (
          <div key={position} id={`step-${index}`} className="mb-6">
            {/* Input Section for Input Steps */}
            {isInputStep && !stepOutput && (
              <ChainInputSection
                step={def.item}
                template={def.template || ""}
                modelId={def.model_id}
                inputs={execution.stepInputs[position] || {}}
                onInputChange={handleStepInputChange(index)}
                onRun={(inputs: Record<number, Record<string, string>>, initialInput?: string, mediaFile?: File | null) => {
                  execution.setStepInputs(inputs);
                  runStepWithTracking(0, mediaFile);
                }}
                loading={executingStep === index}
              />
            )}

            {/* Execute Next Step Button (intermediate) */}
            {!isInputStep && isNextExecutable && (
              <Card className="mb-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-medium text-primary-900 dark:text-white">
                      Step {index + 1}: {def.item.alias || def.item.prompt_id}
                    </h3>
                    <p className="text-sm text-primary-500">
                      Ready to execute (references previous step output)
                    </p>
                  </div>
                  <Button variant="primary" onClick={() => runStepWithTracking(index)}>
                    Execute Next Step
                  </Button>
                </div>
              </Card>
            )}

            {/* Step Status */}
            {stepOutput && (
              <ChainStepStatus
                step={stepOutput}
                expanded={stepOutput.status === "failed"}
                onToggle={() => {}}
              />
            )}

            {/* Output Section for Last Step */}
            {isLastStep && stepOutput && (
              <ChainOutputSection
                step={stepOutput}
                output={stepOutput.response}
                onRerun={execution.handleRerun}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}