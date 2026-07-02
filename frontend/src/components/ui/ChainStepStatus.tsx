import { useState } from "react";
import type { ChainStepResult } from "../../types/prompt";
import Badge from "./Badge";

interface ChainStepStatusProps {
  step: ChainStepResult;
  expanded?: boolean;
  onToggle?: () => void;
}

/**
 * ChainStepStatus renders a collapsible status bar for intermediate chain steps.
 * Shows prompt ID, alias, references, status indicator, cached indicator,
 * execution time, and error message if failed.
 */
export default function ChainStepStatus({
  step,
  expanded = false,
  onToggle,
}: ChainStepStatusProps) {
  const [isExpanded, setIsExpanded] = useState(expanded);

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

  return (
    <div className="rounded-lg border border-surface-200 bg-surface-50 dark:border-primary-700 dark:bg-primary-800 overflow-hidden shadow-sm">
      {/* Collapsible header */}
      <button
        onClick={toggleExpanded}
        className="w-full px-6 py-4 flex items-center justify-between hover:bg-surface-100 dark:hover:bg-primary-700 transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className="text-lg">{status.icon}</span>
          <div>
            <span className="text-sm font-medium text-primary-900 dark:text-white">
              {step.prompt_id}
              {step.prompt_version > 0 && (
                <span className="ml-1 text-primary-500 dark:text-primary-400">v{step.prompt_version}</span>
              )}
            </span>
            {step.alias && (
              <Badge variant="info" className="ml-2">
                {step.alias}
              </Badge>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {step.cached && (
            <Badge variant="neutral">Cached</Badge>
          )}
          <span className={`text-sm font-medium ${status.color}`}>
            {status.label}
          </span>
          <span className="text-primary-400 dark:text-primary-500">{isExpanded ? "▼" : "▶"}</span>
        </div>
      </button>

      {/* Expanded details */}
      {isExpanded && (
        <div className="px-6 pb-4 border-t border-surface-200 dark:border-primary-700">
          {/* References */}
          <div className="mt-3">
            <h4 className="text-sm font-medium text-primary-700 dark:text-primary-300">References</h4>
            <p className="mt-1 text-sm text-primary-600 dark:text-primary-400 font-mono bg-surface-100 dark:bg-primary-900/50 p-2 rounded border border-surface-200 dark:border-primary-700">
              {step.user_message || "No references"}
            </p>
          </div>

          {/* Error message */}
          {step.error && (
            <div className="mt-3">
              <h4 className="text-sm font-medium text-accent-700 dark:text-accent-400">Error</h4>
              <p className="mt-1 text-sm text-accent-600 dark:text-accent-400 font-mono bg-accent-50 dark:bg-accent-900/30 p-2 rounded border border-accent-200 dark:border-accent-800">
                {step.error}
              </p>
            </div>
          )}

          {/* Response preview */}
          {step.response && step.status === "success" && (
            <div className="mt-3">
              <h4 className="text-sm font-medium text-primary-700 dark:text-primary-300">Response Preview</h4>
              <p className="mt-1 text-sm text-primary-600 dark:text-primary-400 font-mono bg-surface-100 dark:bg-primary-900/50 p-2 rounded max-h-48 overflow-y-auto border border-surface-200 dark:border-primary-700">
                {step.response}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
