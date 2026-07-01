import React, { useState } from "react";
import type { ChainStepResult } from "../../types/prompt";

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
    <div className="bg-white shadow rounded-lg overflow-hidden">
      {/* Collapsible header */}
      <button
        onClick={toggleExpanded}
        className="w-full px-6 py-4 flex items-center justify-between hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className="text-lg">{status.icon}</span>
          <div>
            <span className="text-sm font-medium text-gray-900">
              {step.prompt_id}
              {step.prompt_version > 0 && (
                <span className="ml-1 text-gray-500">v{step.prompt_version}</span>
              )}
            </span>
            {step.alias && (
              <span className="ml-2 px-2 py-0.5 text-xs font-medium text-indigo-600 bg-indigo-100 rounded-full">
                {step.alias}
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {step.cached && (
            <span className="px-2 py-0.5 text-xs font-medium text-gray-600 bg-gray-100 rounded-full">
              Cached
            </span>
          )}
          <span className={`text-sm font-medium ${status.color}`}>
            {status.label}
          </span>
          <span className="text-gray-400">{isExpanded ? "▼" : "▶"}</span>
        </div>
      </button>

      {/* Expanded details */}
      {isExpanded && (
        <div className="px-6 pb-4 border-t border-gray-100">
          {/* References */}
          <div className="mt-3">
            <h4 className="text-sm font-medium text-gray-700">References</h4>
            <p className="mt-1 text-sm text-gray-600 font-mono bg-gray-50 p-2 rounded">
              {step.user_message || "No references"}
            </p>
          </div>

          {/* Error message */}
          {step.error && (
            <div className="mt-3">
              <h4 className="text-sm font-medium text-red-700">Error</h4>
              <p className="mt-1 text-sm text-red-600 font-mono bg-red-50 p-2 rounded">
                {step.error}
              </p>
            </div>
          )}

          {/* Response preview */}
          {step.response && step.status === "success" && (
            <div className="mt-3">
              <h4 className="text-sm font-medium text-gray-700">Response Preview</h4>
              <p className="mt-1 text-sm text-gray-600 font-mono bg-gray-50 p-2 rounded max-h-48 overflow-y-auto">
                {step.response}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}