import type { SingleGuestValidation } from "../../types";
import { Badge } from "../../components/ui";
import { JsonPanel } from "./JsonPanel";

interface GuestComparisonViewProps {
  validation: SingleGuestValidation;
}

function MatchBadge({ isMatch }: { isMatch: boolean | null }) {
  if (isMatch === null) return <Badge variant="warning">Error</Badge>;
  if (isMatch) return <Badge variant="success">Match</Badge>;
  return <Badge variant="danger">Mismatch</Badge>;
}

export function GuestComparisonView({ validation }: GuestComparisonViewProps) {
  return (
    <div className="flex flex-col h-full">
      {/* Guest Header */}
      <div className="px-4 py-3 border-b border-surface-200 dark:border-primary-700 flex items-center justify-between flex-shrink-0">
        <div>
          <h3 className="text-base font-semibold text-primary-900 dark:text-white">
            {validation.guest_name}
          </h3>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-xs text-primary-500 dark:text-primary-400">
              Guest ID: {validation.guest_id}
            </span>
            {validation.result_id && (
              <>
                <span className="text-xs text-primary-300 dark:text-primary-600">
                  •
                </span>
                <span className="text-xs text-primary-500 dark:text-primary-400">
                  Result ID: {validation.result_id}
                </span>
              </>
            )}
          </div>
        </div>
        <MatchBadge isMatch={validation.is_match} />
      </div>

      {/* LLM Reasoning Banner (always visible when reasoning exists) */}
      {validation.llm_reasoning && (
        <div className="px-4 py-2 border-b border-surface-200 dark:border-primary-700 bg-surface-50 dark:bg-primary-800/30 flex-shrink-0">
          <p className="text-xs text-primary-700 dark:text-primary-300 whitespace-pre-wrap leading-relaxed">
            {validation.llm_reasoning}
          </p>
        </div>
      )}

      {/* Side-by-Side Panels - fill remaining height */}
      <div className="flex-1 min-h-0 flex">
        <JsonPanel title="Ground Truth" content={validation.ground_truth} />
        <div className="w-px border-l border-surface-200 dark:border-primary-700 flex-shrink-0" />
        <JsonPanel
          title="LLM Response"
          content={validation.llm_response_content}
        />
      </div>
    </div>
  );
}