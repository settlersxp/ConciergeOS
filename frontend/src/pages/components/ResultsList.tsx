import { useState } from "react";
import type { TestResult } from "../../types";

interface ResultsListProps {
  results: TestResult[];
  selectedForCompare: TestResult[];
  onToggleCompare: (result: TestResult) => void;
  onToggleValid: (id: number, valid: boolean) => void;
}

const formatDuration = (sent: string, received: string): string => {
  const s = new Date(sent).getTime();
  const r = new Date(received).getTime();
  const ms = r - s;
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
};

interface ResultItemProps {
  result: TestResult;
  expanded: boolean;
  isSelected: boolean;
  onToggleExpand: () => void;
  onToggleValid: () => void;
  onToggleCompare: () => void;
}

const ResultItem: React.FC<ResultItemProps> = ({
  result,
  expanded,
  isSelected,
  onToggleExpand,
  onToggleValid,
  onToggleCompare,
}) => {
  const validLabel =
    result.valid_response === true
      ? "Valid"
      : result.valid_response === false
        ? "Invalid"
        : "Unset";
  const validClass =
    result.valid_response === true
      ? "text-secondary-500 dark:text-secondary-400"
      : result.valid_response === false
        ? "text-accent-600 dark:text-accent-400"
        : "text-primary-400";

  return (
    <div className={expanded ? "" : "border-b border-surface-100 dark:border-primary-700/50"}>
      {/* Header Row */}
      <div
        className="flex cursor-pointer items-center gap-3 px-4 py-3 hover:bg-surface-100 dark:hover:bg-primary-700/30"
        onClick={onToggleExpand}
      >
        {/* Compare Checkbox */}
        <input
          type="checkbox"
          checked={isSelected}
          onChange={(e) => {
            e.stopPropagation();
            onToggleCompare();
          }}
          onClick={(e) => e.stopPropagation()}
          className="h-4 w-4 rounded border-surface-300 text-accent-500 focus:ring-accent-500"
        />

        <span className="text-xs text-primary-400 dark:text-primary-500 min-w-[80px]">
          {result.batch_type}
        </span>
        <span className="text-xs font-mono text-primary-500 dark:text-primary-400">
          #{result.request_index}
        </span>
        <span className="text-xs text-primary-400 dark:text-primary-500 min-w-[100px] truncate">
          {result.model_name}
        </span>
        <span className="text-xs font-mono text-primary-500 dark:text-primary-400">
          {formatDuration(result.request_sent_time, result.response_received_time)}
        </span>
        <span className={`text-xs font-medium ${validClass}`}>
          {validLabel}
        </span>
        {result.json_malformed === true && (
          <span className="text-xs text-accent-400 dark:text-accent-300">
            malformed JSON
          </span>
        )}
        <span className="ml-auto text-xs text-primary-400">{expanded ? "▲" : "▼"}</span>
      </div>

      {/* Expanded Detail */}
      {expanded && (
        <div className="border-t border-surface-100 dark:border-primary-700/50 px-4 py-4 bg-surface-50 dark:bg-primary-800/50">
          <div className="mb-3 grid gap-2 text-xs text-primary-500 dark:text-primary-400 md:grid-cols-3">
            <div>
              <span className="font-medium">Context:</span> {result.context_length}
            </div>
            <div>
              <span className="font-medium">Response len:</span>{" "}
              {result.response_length}
            </div>
            <div>
              <span className="font-medium">vLLM:</span> {result.vllm_version || "—"}
            </div>
            <div>
              <span className="font-medium">Format:</span> {result.response_format || "—"}
            </div>
            <div>
              <span className="font-medium">Thinking:</span>{" "}
              {result.thinking_enabled ? "Yes" : "No"}
            </div>
            <div>
              <span className="font-medium">Customer:</span> {result.customer_name || "—"}
            </div>
          </div>

          <div className="mb-3">
            <span className="text-xs font-medium text-primary-500 dark:text-primary-400">
              User Prompt:
            </span>
            <pre className="mt-1 whitespace-pre-wrap rounded-md bg-white dark:bg-primary-900 border border-surface-200 dark:border-primary-700 p-3 text-xs text-primary-700 dark:text-primary-300 max-h-48 overflow-auto">
              {result.user_prompt}
            </pre>
          </div>

          <div className="mb-3">
            <span className="text-xs font-medium text-primary-500 dark:text-primary-400">
              Response:
            </span>
            <pre className="mt-1 whitespace-pre-wrap rounded-md bg-white dark:bg-primary-900 border border-surface-200 dark:border-primary-700 p-3 text-xs text-primary-700 dark:text-primary-300 max-h-64 overflow-auto">
              {result.response_content}
            </pre>
          </div>

          <div className="flex gap-2">
            <button
              onClick={onToggleValid}
              className="rounded-md border border-surface-300 dark:border-primary-600 px-3 py-1.5 text-xs hover:bg-surface-100 dark:hover:bg-primary-700 transition-colors"
            >
              Toggle Valid (→ {result.valid_response === true ? "Invalid" : "Valid"})
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onToggleCompare();
              }}
              className={`rounded-md border px-3 py-1.5 text-xs transition-colors ${
                isSelected
                  ? "border-accent-300 dark:border-accent-600 bg-accent-50 dark:bg-accent-900/30 text-accent-600 dark:text-accent-400"
                  : "border-surface-300 dark:border-primary-600 hover:bg-surface-100 dark:hover:bg-primary-700"
              }`}
            >
              {isSelected ? "✓ Selected for Compare" : "Select for Compare"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default function ResultsList({
  results,
  selectedForCompare,
  onToggleCompare,
  onToggleValid,
}: ResultsListProps) {
  const [expandedResult, setExpandedResult] = useState<number | null>(null);

  return (
    <div className="rounded-lg border border-surface-200 dark:border-primary-700 bg-surface-50 dark:bg-primary-800 shadow-sm">
      <div className="border-b border-surface-200 dark:border-primary-700 px-6 py-4 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-primary-800 dark:text-primary-200">
          Results ({results.length})
        </h3>
        {selectedForCompare.length > 0 && (
          <span className="text-xs bg-accent-100 dark:bg-accent-900/30 text-accent-600 dark:text-accent-400 px-2 py-1 rounded-full">
            {selectedForCompare.length}/2 selected for comparison
          </span>
        )}
      </div>

      {results.length === 0 ? (
        <p className="px-6 py-8 text-center text-sm text-primary-400">
          No results yet. Run a test to see results here.
        </p>
      ) : (
        <div>{results.map((r) => (
          <ResultItem
            key={r.id}
            result={r}
            expanded={expandedResult === r.id}
            isSelected={selectedForCompare.some((s) => s.id === r.id)}
            onToggleExpand={() =>
              setExpandedResult(expandedResult === r.id ? null : r.id)
            }
            onToggleValid={() =>
              onToggleValid(r.id, !(r.valid_response ?? false))
            }
            onToggleCompare={() => onToggleCompare(r)}
          />
        ))}</div>
      )}
    </div>
  );
}