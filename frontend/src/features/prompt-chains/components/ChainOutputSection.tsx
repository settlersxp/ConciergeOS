import { useState, useCallback } from "react";
import type { ChainStepResult } from "../../types/prompt";
import Button from "./Button";
import Card from "./Card";
import Badge from "./Badge";

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
      <Card title="Final Output" titleClassName="text-xl">
        {step.error ? (
          <div className="p-4 bg-accent-50 border border-accent-200 rounded-md dark:bg-accent-900/30 dark:border-accent-800">
            <p className="text-sm font-medium text-accent-800 dark:text-accent-300">Step failed: {step.error}</p>
          </div>
        ) : (
          <p className="text-primary-500 dark:text-primary-400">No output available.</p>
        )}
      </Card>
    );
  }

  // Truncate if more than 2000 chars and not expanded
  const maxLength = 2000;
  const isLong = output.length > maxLength;
  const displayContent = isExpanded || !isLong ? output : output.slice(0, maxLength) + "...";

  return (
    <Card title="Final Output" titleClassName="text-xl flex items-center gap-2">
      {/* Header badges */}
      <div className="flex items-center gap-2 mb-4">
        {step.alias && (
          <Badge variant="info">{step.alias}</Badge>
        )}
        {step.cached && (
          <Badge variant="neutral">Cached</Badge>
        )}
        {isLong && (
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="text-sm text-secondary-600 hover:text-secondary-700 dark:text-secondary-400 dark:hover:text-secondary-300 ml-auto"
          >
            {isExpanded ? "Show less" : "Show more"}
          </button>
        )}
      </div>

      {/* Output content */}
      <div className="prose prose-sm max-w-none text-primary-900 dark:text-primary-100 whitespace-pre-wrap break-words font-mono bg-surface-100 dark:bg-primary-900/50 p-4 rounded-md max-h-96 overflow-y-auto border border-surface-200 dark:border-primary-700">
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
        <span className="text-sm text-primary-400 dark:text-primary-500 ml-auto">
          {output.length.toLocaleString()} characters
        </span>
      </div>
    </Card>
  );
}
