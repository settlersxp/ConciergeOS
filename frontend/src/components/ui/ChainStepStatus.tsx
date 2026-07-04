import { useState } from "react";
import type { ChainStepResult } from "../../types/prompt";
import Badge from "./Badge";

interface ChainStepStatusProps {
  step: ChainStepResult;
  expanded?: boolean;
  onToggle?: () => void;
  /** Index among all step outputs (for root cause detection) */
  allOutputs?: ChainStepResult[];
}

const CONTEXT_TRUNCATE = 300;
const OUTPUT_TRUNCATE = 600;

/**
 * ChainStepStatus renders a debug-rich status card for each chain step.
 * Always visible: status header, input context (from previous steps), output/error.
 * Collapsible: system prompt, user message (raw LLM request details).
 */
export default function ChainStepStatus({
  step,
  expanded = false,
  onToggle,
  allOutputs = [],
}: ChainStepStatusProps) {
  const [isExpanded, setIsExpanded] = useState(expanded);
  const [contextExpanded, setContextExpanded] = useState(false);
  const [outputExpanded, setOutputExpanded] = useState(false);

  const toggleExpanded = () => {
    setIsExpanded(!isExpanded);
    onToggle?.();
  };

  // Determine status display
  const statusConfig = {
    running: { color: "text-yellow-500", label: "Running", icon: "⏳" },
    success: { color: "text-green-500", label: "Success", icon: "✅" },
    failed: { color: "text-red-500", label: "Failed", icon: "❌" },
  };

  const status = statusConfig[step.status] || statusConfig.failed;

  // Find the first failed step before this one (root cause)
  const rootCauseStep =
    step.status === "failed"
      ? allOutputs.find((s) => s.position < step.position && s.status === "failed")
      : null;

  // --- Truncate helpers ---
  const ctxDisplay = step.context_input;
  const ctxTruncated = ctxDisplay && ctxDisplay.length > CONTEXT_TRUNCATE
    ? ctxDisplay.slice(0, CONTEXT_TRUNCATE) + "..."
    : ctxDisplay;
  const ctxNeedsToggle = ctxDisplay && ctxDisplay.length > CONTEXT_TRUNCATE;

  const outDisplay = step.response || step.error || "";
  const outTruncated = outDisplay.length > OUTPUT_TRUNCATE
    ? outDisplay.slice(0, OUTPUT_TRUNCATE) + "..."
    : outDisplay;
  const outNeedsToggle = outDisplay.length > OUTPUT_TRUNCATE;

  return (
    <div className="rounded-lg border border-surface-200 bg-surface-50 dark:border-primary-700 dark:bg-primary-800 overflow-hidden shadow-sm">
      {/* ── Collapsible header ── */}
      <button
        onClick={toggleExpanded}
        className="w-full px-6 py-4 flex items-center justify-between hover:bg-surface-100 dark:hover:bg-primary-700 transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className="text-lg">{status.icon}</span>
          <div>
            <span className="text-sm font-medium text-primary-900 dark:text-white">
              Step {step.position}: {step.alias || step.prompt_id}
              {step.prompt_version > 0 && (
                <span className="ml-1 text-primary-500 dark:text-primary-400">v{step.prompt_version}</span>
              )}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {step.cached && <Badge variant="neutral">Cached</Badge>}
          <span className={`text-sm font-medium ${status.color}`}>{status.label}</span>
          <span className="text-primary-400 dark:text-primary-500">{isExpanded ? "▼" : "▶"}</span>
        </div>
      </button>

      {/* ── Body (always visible when step has a result) ── */}
      <div className="px-6 pb-4 border-t border-surface-200 dark:border-primary-700">
        {/* Root cause warning */}
        {rootCauseStep && (
          <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-md dark:bg-yellow-900/20 dark:border-yellow-800">
            <p className="text-sm font-medium text-yellow-800 dark:text-yellow-300">
              ⚠️ This step may have failed due to <strong>Step {rootCauseStep.position}</strong>{" "}
              ({rootCauseStep.alias || rootCauseStep.prompt_id}) failing first.
            </p>
            {rootCauseStep.error && (
              <p className="mt-1 text-xs text-yellow-700 dark:text-yellow-400 font-mono">
                Root error: {rootCauseStep.error}
              </p>
            )}
          </div>
        )}

        {/* ── Input Context (what previous steps produced) ── */}
        {step.context_input && (
          <div className="mt-4">
            <h4 className="text-sm font-semibold text-primary-700 dark:text-primary-300 flex items-center gap-2">
              <span className="text-xs uppercase tracking-wide text-primary-500">Input Context</span>
              <span className="text-xs text-primary-400 dark:text-primary-500">
                (from previous step(s))
              </span>
            </h4>
            <div className="mt-1 text-sm text-primary-700 dark:text-primary-300 font-mono bg-surface-100 dark:bg-primary-900/50 p-3 rounded border border-surface-200 dark:border-primary-700 max-h-48 overflow-y-auto whitespace-pre-wrap break-words">
              {contextExpanded ? ctxDisplay : ctxTruncated}
            </div>
            {ctxNeedsToggle && (
              <button
                onClick={() => setContextExpanded(!contextExpanded)}
                className="mt-1 text-xs text-secondary-600 hover:text-secondary-700 dark:text-secondary-400"
              >
                {contextExpanded ? "Show less" : "Show more"}
              </button>
            )}
          </div>
        )}

        {/* ── Output / Error ── */}
        {step.status === "success" && step.response && (
          <div className="mt-4">
            <h4 className="text-sm font-semibold text-green-700 dark:text-green-400 flex items-center gap-2">
              <span className="text-xs uppercase tracking-wide text-green-500">Output</span>
            </h4>
            <div className="mt-1 text-sm text-primary-700 dark:text-primary-300 font-mono bg-surface-100 dark:bg-primary-900/50 p-3 rounded border border-surface-200 dark:border-primary-700 max-h-72 overflow-y-auto whitespace-pre-wrap break-words">
              {outputExpanded ? outDisplay : outTruncated}
            </div>
            {outNeedsToggle && (
              <button
                onClick={() => setOutputExpanded(!outputExpanded)}
                className="mt-1 text-xs text-secondary-600 hover:text-secondary-700 dark:text-secondary-400"
              >
                {outputExpanded ? "Show less" : "Show more"}
              </button>
            )}
          </div>
        )}

        {step.status === "failed" && step.error && (
          <div className="mt-4">
            <h4 className="text-sm font-semibold text-accent-700 dark:text-accent-400 flex items-center gap-2">
              <span className="text-xs uppercase tracking-wide text-accent-500">Error</span>
            </h4>
            <div className="mt-1 text-sm text-accent-700 dark:text-accent-300 font-mono bg-accent-50 dark:bg-accent-900/30 p-3 rounded border border-accent-200 dark:border-accent-800 max-h-48 overflow-y-auto whitespace-pre-wrap break-words">
              {step.error}
            </div>
          </div>
        )}

        {/* ── Deep debug (collapsible) ── */}
        {isExpanded && (
          <>
            {step.system_prompt && (
              <div className="mt-4">
                <h4 className="text-sm font-medium text-primary-700 dark:text-primary-300">System Prompt</h4>
                <pre className="mt-1 text-xs text-primary-600 dark:text-primary-400 font-mono bg-surface-100 dark:bg-primary-900/50 p-3 rounded border border-surface-200 dark:border-primary-700 max-h-48 overflow-y-auto whitespace-pre-wrap break-words">
                  {step.system_prompt}
                </pre>
              </div>
            )}

            {step.user_message && (
              <div className="mt-4">
                <h4 className="text-sm font-medium text-primary-700 dark:text-primary-300">User Message (to LLM)</h4>
                <pre className="mt-1 text-xs text-primary-600 dark:text-primary-400 font-mono bg-surface-100 dark:bg-primary-900/50 p-3 rounded border border-surface-200 dark:border-primary-700 max-h-48 overflow-y-auto whitespace-pre-wrap break-words">
                  {step.user_message}
                </pre>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}