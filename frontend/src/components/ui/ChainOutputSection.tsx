import React, { useState, useCallback } from "react";
import type { ChainStepResult } from "../../types/prompt";
import Button from "./Button";

interface ChainOutputSectionProps {
  step: ChainStepResult;
  output: string | null;
  onRerun?: () => void;
}

/**
 * ChainOutputSection renders the final step's LLM output.
 * Features: markdown rendering, copy to clipboard, expand/collapse,
 * re-run chain button, cached indicator.
 */
export default function ChainOutputSection({
  step,
  output,
  onRerun,
}: ChainOutputSectionProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    if (!output) return;
    try {
      await navigator.clipboard.writeText(output);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy:", err);
    }
  }, [output]);

  if (!output) {
    return (
      <div className="bg-white shadow rounded-lg p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">
          Final Output
        </h2>
        {step.error ? (
          <div className="p-4 bg-red-50 border border-red-200 rounded-md">
            <p className="text-sm font-medium text-red-800">Step failed: {step.error}</p>
          </div>
        ) : (
          <p className="text-gray-500">No output available.</p>
        )}
      </div>
    );
  }

  // Truncate if more than 2000 chars and not expanded
  const maxLength = 2000;
  const isLong = output.length > maxLength;
  const displayContent = isExpanded || !isLong ? output : output.slice(0, maxLength) + "...";

  return (
    <div className="bg-white shadow rounded-lg overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
        <h2 className="text-xl font-semibold text-gray-900">
          Final Output
          {step.alias && (
            <span className="ml-2 px-2 py-0.5 text-xs font-medium text-indigo-600 bg-indigo-100 rounded-full">
              {step.alias}
            </span>
          )}
        </h2>
        <div className="flex items-center gap-2">
          {step.cached && (
            <span className="px-2 py-0.5 text-xs font-medium text-gray-600 bg-gray-100 rounded-full">
              Cached
            </span>
          )}
          {isLong && (
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="text-sm text-indigo-600 hover:text-indigo-800"
            >
              {isExpanded ? "Show less" : "Show more"}
            </button>
          )}
        </div>
      </div>

      {/* Output content */}
      <div className="p-6">
        <div className="prose prose-sm max-w-none text-gray-800 whitespace-pre-wrap break-words font-mono bg-gray-50 p-4 rounded-md max-h-96 overflow-y-auto">
          {displayContent}
        </div>

        {/* Action buttons */}
        <div className="mt-4 flex items-center gap-3">
          <Button variant="secondary" onClick={handleCopy}>
            {copied ? "Copied!" : "Copy"}
          </Button>
          {onRerun && (
            <Button variant="secondary" onClick={onRerun}>
              Re-run Chain
            </Button>
          )}
          <span className="text-sm text-gray-400 ml-auto">
            {output.length.toLocaleString()} characters
          </span>
        </div>
      </div>
    </div>
  );
}