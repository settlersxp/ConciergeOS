import { useState, useEffect, useRef, useCallback } from "react";
import { Badge, Button } from "../../components/ui";
import type { SingleGuestValidation } from "../../types";
import { computeJsonDiff } from "../../utils/diff";

interface ValidationModalProps {
  results: SingleGuestValidation[];
  summary?: {
    total_guests: number;
    matched: number;
    total_validated: number;
    accuracy: number;
  };
  onClose: () => void;
  onMarkValid?: (resultId: number, valid: boolean) => void;
}

// ── Match Badge ──────────────────────────────────────────────────────────────

function MatchBadge({ isMatch }: { isMatch: boolean | null }) {
  if (isMatch === null) return <Badge variant="warning">Error</Badge>;
  if (isMatch) return <Badge variant="success">Match</Badge>;
  return <Badge variant="danger">Mismatch</Badge>;
}

// ── Single Guest Comparison View ─────────────────────────────────────────────

function GuestComparisonView({
  validation,
}: {
  validation: SingleGuestValidation;
}) {
  const scrollLeftRef = useRef<HTMLDivElement>(null);
  const scrollRightRef = useRef<HTMLDivElement>(null);

  const diffed = computeJsonDiff(
    validation.ground_truth,
    validation.llm_response_content,
  );

  const handleWheel = useCallback((e: WheelEvent) => {
    e.preventDefault();
    const left = scrollLeftRef.current;
    const right = scrollRightRef.current;
    if (!left || !right) return;

    const delta =
      Math.abs(e.deltaY) > Math.abs(e.deltaX) ? e.deltaY : e.deltaX;

    left.scrollTop = Math.max(0, left.scrollTop + delta);
    right.scrollTop = Math.max(0, right.scrollTop + delta);
  }, []);

  useEffect(() => {
    const left = scrollLeftRef.current;
    const right = scrollRightRef.current;
    if (!left || !right) return;

    left.addEventListener("wheel", handleWheel, { passive: false });
    right.addEventListener("wheel", handleWheel, { passive: false });

    left.scrollTop = 0;
    right.scrollTop = 0;

    return () => {
      left.removeEventListener("wheel", handleWheel);
      right.removeEventListener("wheel", handleWheel);
    };
  }, [handleWheel]);

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {/* Guest Header */}
      <div className="px-4 py-3 border-b border-surface-200 dark:border-primary-700 flex items-center justify-between">
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
        <div className="px-4 py-2 border-b border-surface-200 dark:border-primary-700 bg-surface-50 dark:bg-primary-800/30">
          <p className="text-xs text-primary-700 dark:text-primary-300 whitespace-pre-wrap leading-relaxed">
            {validation.llm_reasoning}
          </p>
        </div>
      )}

      {/* Side-by-Side Panels */}
      <div className="flex-1 grid grid-cols-2 divide-x divide-surface-200 dark:divide-primary-700 min-h-0 min-w-0">
        {/* Left - Ground Truth */}
        <div className="flex flex-col min-h-0 min-w-0 overflow-hidden">
          <div className="px-4 py-2 border-b border-surface-100 dark:border-primary-700/50 bg-surface-50 dark:bg-primary-800/50 flex-shrink-0">
            <span className="text-xs font-semibold text-primary-600 dark:text-primary-400 uppercase tracking-wider">
              Ground Truth
            </span>
          </div>
          <div
            ref={scrollLeftRef}
            className="flex-1 overflow-y-auto overflow-x-hidden p-3 text-xs font-mono leading-relaxed"
            style={{ minHeight: 0 }}
          >
            <pre
              className="validation-diff-pre whitespace-pre-wrap break-words"
              dangerouslySetInnerHTML={{ __html: diffed.left }}
            />
          </div>
        </div>

        {/* Right - LLM Response */}
        <div className="flex flex-col min-h-0 min-w-0 overflow-hidden">
          <div className="px-4 py-2 border-b border-surface-100 dark:border-primary-700/50 bg-surface-50 dark:bg-primary-800/50 flex-shrink-0">
            <span className="text-xs font-semibold text-primary-600 dark:text-primary-400 uppercase tracking-wider">
              LLM Response
            </span>
          </div>
          <div
            ref={scrollRightRef}
            className="flex-1 overflow-y-auto overflow-x-hidden p-3 text-xs font-mono leading-relaxed"
            style={{ minHeight: 0 }}
          >
            <pre className="validation-diff-pre whitespace-pre-wrap break-words">
              {diffed.right}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Main Modal ───────────────────────────────────────────────────────────────

export default function ValidationModal({
  results,
  summary,
  onClose,
  onMarkValid,
}: ValidationModalProps) {
  const [activeIndex, setActiveIndex] = useState(0);

  // Trap focus and handle Escape
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      // Navigate with arrow keys
      if (e.key === "ArrowLeft" && activeIndex > 0) {
        setActiveIndex((i) => i - 1);
      } else if (
        e.key === "ArrowRight" &&
        activeIndex < results.length - 1
      ) {
        setActiveIndex((i) => i + 1);
      }
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [onClose, activeIndex, results.length]);

  const activeValidation = results[activeIndex];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="bg-surface-50 dark:bg-primary-800 rounded-xl shadow-2xl w-full max-w-6xl max-h-[90vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-surface-200 dark:border-primary-700">
          <div>
            <h2 className="text-lg font-bold text-primary-900 dark:text-white">
              Validation Results
            </h2>
            {summary && (
              <p className="text-sm text-primary-500 dark:text-primary-400 mt-1">
                Accuracy:{" "}
                <span className="font-semibold">
                  {(summary.accuracy * 100).toFixed(1)}%
                </span>{" "}
                ({summary.matched}/{summary.total_validated} matched)
              </p>
            )}
          </div>
          <button
            onClick={onClose}
            className="text-primary-400 hover:text-primary-600 dark:hover:text-primary-200 text-2xl leading-none"
          >
            &times;
          </button>
        </div>

        {/* Summary Strip */}
        {summary && (
          <div className="grid grid-cols-4 gap-3 px-6 py-3 border-b border-surface-200 dark:border-primary-700 bg-white dark:bg-primary-900">
            <div className="text-center">
              <div className="text-lg font-bold text-primary-900 dark:text-white">
                {summary.total_guests}
              </div>
              <div className="text-xs text-primary-500 dark:text-primary-400">
                Total Guests
              </div>
            </div>
            <div className="text-center">
              <div className="text-lg font-bold text-primary-900 dark:text-white">
                {summary.total_validated}
              </div>
              <div className="text-xs text-primary-500 dark:text-primary-400">
                Validated
              </div>
            </div>
            <div className="text-center">
              <div className="text-lg font-bold text-green-600 dark:text-green-400">
                {summary.matched}
              </div>
              <div className="text-xs text-primary-500 dark:text-primary-400">
                Matched
              </div>
            </div>
            <div className="text-center">
              <div className="text-lg font-bold text-red-600 dark:text-red-400">
                {summary.total_validated - summary.matched}
              </div>
              <div className="text-xs text-primary-500 dark:text-primary-400">
                Mismatched
              </div>
            </div>
          </div>
        )}

        {/* Guest Navigation Tabs */}
        {results.length > 1 && (
          <div className="px-6 py-2 border-b border-surface-200 dark:border-primary-700 flex gap-1 overflow-x-auto bg-white dark:bg-primary-900">
            {results.map((r, i) => (
              <button
                key={r.guest_id}
                onClick={() => setActiveIndex(i)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium whitespace-nowrap transition-colors ${
                  i === activeIndex
                    ? "bg-accent-100 dark:bg-accent-900/30 text-accent-700 dark:text-accent-300"
                    : "text-primary-500 dark:text-primary-400 hover:bg-surface-100 dark:hover:bg-primary-700/50"
                }`}
              >
                <MatchBadge isMatch={r.is_match} />
                <span>{r.guest_name}</span>
              </button>
            ))}
          </div>
        )}

        {/* Comparison Body (flex-1 to fill remaining space) */}
        <div className="flex-1 min-h-0 overflow-hidden">
          {activeValidation && <GuestComparisonView validation={activeValidation} />}
        </div>

        {/* Footer with Navigation */}
        {results.length > 1 && (
          <div className="px-6 py-3 border-t border-surface-200 dark:border-primary-700 flex items-center justify-between bg-white dark:bg-primary-900 gap-3">
            <Button
              variant="secondary"
              size="sm"
              disabled={activeIndex === 0}
              onClick={() => setActiveIndex((i) => i - 1)}
            >
              ← Previous
            </Button>

            {/* Valid / Invalid buttons */}
            {activeValidation?.result_id && onMarkValid && (
              <div className="flex items-center gap-2">
                <Button
                  variant="success"
                  size="sm"
                  onClick={() => onMarkValid(activeValidation.result_id!, true)}
                >
                  ✓ Mark Valid
                </Button>
                <Button
                  variant="danger"
                  size="sm"
                  onClick={() => onMarkValid(activeValidation.result_id!, false)}
                >
                  ✗ Mark Invalid
                </Button>
              </div>
            )}

            <span className="text-xs text-primary-500 dark:text-primary-400">
              {activeIndex + 1} / {results.length}
            </span>

            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                disabled={activeIndex === results.length - 1}
                onClick={() => setActiveIndex((i) => i + 1)}
              >
                Next →
              </Button>
              <Button variant="primary" size="sm" onClick={onClose}>
                Done
              </Button>
            </div>
          </div>
        )}

        {/* Close Button Footer (single guest) */}
        {results.length <= 1 && (
          <div className="px-6 py-3 border-t border-surface-200 dark:border-primary-700 flex items-center justify-between bg-white dark:bg-primary-900 gap-3">
            {/* Valid / Invalid buttons */}
            {activeValidation?.result_id && onMarkValid && (
              <div className="flex items-center gap-2">
                <Button
                  variant="success"
                  size="sm"
                  onClick={() => onMarkValid(activeValidation.result_id!, true)}
                >
                  ✓ Mark Valid
                </Button>
                <Button
                  variant="danger"
                  size="sm"
                  onClick={() => onMarkValid(activeValidation.result_id!, false)}
                >
                  ✗ Mark Invalid
                </Button>
              </div>
            )}
            <Button variant="primary" onClick={onClose}>
              Done
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}