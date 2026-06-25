import { useState } from "react";
import { Badge, Button } from "../../components/ui";
import type { SingleGuestValidation } from "../../types";

interface ValidationModalProps {
  results: SingleGuestValidation[];
  summary?: {
    total_guests: number;
    matched: number;
    total_validated: number;
    accuracy: number;
  };
  onClose: () => void;
}

export default function ValidationModal({ results, summary, onClose }: ValidationModalProps) {
  const [expandedRow, setExpandedRow] = useState<number | null>(null);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white dark:bg-primary-900 rounded-xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col mx-4">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-surface-200 dark:border-primary-700">
          <div>
            <h2 className="text-lg font-semibold text-primary-900 dark:text-white">
              LLM Validation Results
            </h2>
            {summary && (
              <p className="text-sm text-primary-500 dark:text-primary-400 mt-1">
                Accuracy: <span className="font-semibold">{(summary.accuracy * 100).toFixed(1)}%</span> ({summary.matched}/{summary.total_validated} matched)
              </p>
            )}
          </div>
          <Button variant="secondary" onClick={onClose}>
            Close
          </Button>
        </div>

        {/* Summary Cards */}
        {summary && (
          <div className="grid grid-cols-4 gap-3 p-4 border-b border-surface-200 dark:border-primary-700">
            <div className="bg-surface-50 dark:bg-primary-800 rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-primary-900 dark:text-white">{summary.total_guests}</div>
              <div className="text-xs text-primary-500 dark:text-primary-400">Total Guests</div>
            </div>
            <div className="bg-surface-50 dark:bg-primary-800 rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-primary-900 dark:text-white">{summary.total_validated}</div>
              <div className="text-xs text-primary-500 dark:text-primary-400">Validated</div>
            </div>
            <div className="bg-surface-50 dark:bg-primary-800 rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-green-600 dark:text-green-400">{summary.matched}</div>
              <div className="text-xs text-primary-500 dark:text-primary-400">Matched</div>
            </div>
            <div className="bg-surface-50 dark:bg-primary-800 rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-red-600 dark:text-red-400">{summary.total_validated - summary.matched}</div>
              <div className="text-xs text-primary-500 dark:text-primary-400">Mismatched</div>
            </div>
          </div>
        )}

        {/* Results Table */}
        <div className="flex-1 overflow-auto p-4">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-white dark:bg-primary-900">
              <tr className="border-b border-surface-200 dark:border-primary-700">
                <th className="text-left py-2 px-2 text-xs font-medium text-primary-500 dark:text-primary-400 w-8">#</th>
                <th className="text-left py-2 px-2 text-xs font-medium text-primary-500 dark:text-primary-400">Guest Name</th>
                <th className="text-left py-2 px-2 text-xs font-medium text-primary-500 dark:text-primary-400 w-24">Result ID</th>
                <th className="text-left py-2 px-2 text-xs font-medium text-primary-500 dark:text-primary-400 w-24">Match</th>
              </tr>
            </thead>
            <tbody>
              {results.map((r, i) => {
                const isExpanded = expandedRow === r.guest_id;
                return (
                  <>
                    <tr
                      key={r.guest_id}
                      className={`border-b border-surface-100 dark:border-primary-700/50 cursor-pointer transition-colors ${
                        isExpanded
                          ? "bg-surface-200 dark:bg-primary-700/80"
                          : "hover:bg-surface-100 dark:hover:bg-primary-700/50"
                      }`}
                      onClick={() => setExpandedRow(isExpanded ? null : r.guest_id)}
                    >
                      <td className="py-2 px-2 text-primary-500 dark:text-primary-400">
                        <span className="inline-flex items-center gap-1">
                          <span className={`text-xs transition-transform ${isExpanded ? "rotate-90" : ""}`}>▶</span>
                          {i + 1}
                        </span>
                      </td>
                      <td className="py-2 px-2 text-primary-800 dark:text-white font-medium">
                        {r.guest_name}
                      </td>
                      <td className="py-2 px-2 text-primary-600 dark:text-primary-300">
                        {r.result_id ?? "—"}
                      </td>
                      <td className="py-2 px-2">
                        {r.is_match === null ? (
                          <Badge variant="warning">Error</Badge>
                        ) : r.is_match ? (
                          <Badge variant="success">Match</Badge>
                        ) : (
                          <Badge variant="danger">Mismatch</Badge>
                        )}
                      </td>
                    </tr>
                    {isExpanded && (
                      <tr key={`${r.guest_id}-detail`} className="bg-surface-50 dark:bg-primary-800/30">
                        <td colSpan={4} className="p-0">
                          <div className="px-4 py-3">
                            <div className="text-xs font-medium text-primary-500 dark:text-primary-400 mb-1">
                              LLM Reasoning:
                            </div>
                            <pre className="text-xs bg-white dark:bg-primary-900/50 border border-surface-200 dark:border-primary-700 rounded p-3 overflow-auto max-h-64 whitespace-pre-wrap font-mono text-primary-700 dark:text-primary-300">
                              {r.llm_reasoning || "No reasoning provided."}
                            </pre>
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                );
              })}
            </tbody>
          </table>

          {results.length === 0 && (
            <div className="text-center py-8 text-primary-500 dark:text-primary-400">
              No validation results to display.
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-surface-200 dark:border-primary-700 flex justify-end">
          <Button variant="primary" onClick={onClose}>
            Done
          </Button>
        </div>
      </div>
    </div>
  );
}