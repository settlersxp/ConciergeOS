import { useState, useEffect } from "react";
import { Badge, Button } from "../../components/ui";
import type { SingleGuestValidation } from "../../types";
import { GuestComparisonView } from "./GuestComparisonView";

// ── Helpers ──────────────────────────────────────────────────────────────────

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

// ── Match Badge for tab navigation ───────────────────────────────────────────

function MatchBadge({ isMatch }: { isMatch: boolean | null }) {
  if (isMatch === null) return <Badge variant="warning">Error</Badge>;
  if (isMatch) return <Badge variant="success">Match</Badge>;
  return <Badge variant="danger">Mismatch</Badge>;
}

// ── Modal Header ─────────────────────────────────────────────────────────────

function ModalHeader({
  summary,
  onClose,
}: {
  summary?: ValidationModalProps["summary"];
  onClose: () => void;
}) {
  return (
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
  );
}

// ── Summary Strip ────────────────────────────────────────────────────────────

function SummaryStrip({
  summary,
}: {
  summary: NonNullable<ValidationModalProps["summary"]>;
}) {
  return (
    <div className="grid grid-cols-4 gap-3 px-6 py-3 border-b border-surface-200 dark:border-primary-700">
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
  );
}

// ── Guest Navigation Tabs ────────────────────────────────────────────────────

function GuestTabs({
  results,
  activeIndex,
  onSelect,
}: {
  results: SingleGuestValidation[];
  activeIndex: number;
  onSelect: (index: number) => void;
}) {
  return (
    <div className="px-6 py-2 border-b border-surface-200 dark:border-primary-700 flex gap-1 overflow-x-auto">
      {results.map((r, i) => (
        <button
          key={r.guest_id}
          onClick={() => onSelect(i)}
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
  );
}

// ── Footer with Navigation (multiple guests) ─────────────────────────────────

function NavigationFooter({
  activeIndex,
  total,
  onPrevious,
  onNext,
  onMarkValid,
  activeResultId,
  onClose,
}: {
  activeIndex: number;
  total: number;
  onPrevious: () => void;
  onNext: () => void;
  onMarkValid?: (resultId: number, valid: boolean) => void;
  activeResultId?: number;
  onClose: () => void;
}) {
  return (
    <div className="px-6 py-3 border-t border-surface-200 dark:border-primary-700 flex items-center justify-between gap-3">
      <Button
        variant="secondary"
        size="sm"
        disabled={activeIndex === 0}
        onClick={onPrevious}
      >
        ← Previous
      </Button>

      {activeResultId && onMarkValid && (
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => onMarkValid(activeResultId, true)}
          >
            ✓ Mark Valid
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => onMarkValid(activeResultId, false)}
          >
            ✗ Mark Invalid
          </Button>
        </div>
      )}

      <span className="text-xs text-primary-500 dark:text-primary-400">
        {activeIndex + 1} / {total}
      </span>

      <div className="flex items-center gap-2">
        <Button
          variant="secondary"
          size="sm"
          disabled={activeIndex === total - 1}
          onClick={onNext}
        >
          Next →
        </Button>
        <Button variant="primary" size="sm" onClick={onClose}>
          Done
        </Button>
      </div>
    </div>
  );
}

// ── Footer (single guest) ────────────────────────────────────────────────────

function SimpleFooter({
  onMarkValid,
  activeResultId,
  onClose,
}: {
  onMarkValid?: (resultId: number, valid: boolean) => void;
  activeResultId?: number;
  onClose: () => void;
}) {
  return (
    <div className="px-6 py-3 border-t border-surface-200 dark:border-primary-700 flex items-center justify-between gap-3">
      {activeResultId && onMarkValid && (
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => onMarkValid(activeResultId, true)}
          >
            ✓ Mark Valid
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => onMarkValid(activeResultId, false)}
          >
            ✗ Mark Invalid
          </Button>
        </div>
      )}
      <Button variant="primary" onClick={onClose}>
        Done
      </Button>
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
      } else if (e.key === "ArrowRight" && activeIndex < results.length - 1) {
        setActiveIndex((i) => i + 1);
      }
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [onClose, activeIndex, results.length]);

  const activeValidation = results[activeIndex];
  const hasMultiple = results.length > 1;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="bg-surface-50 dark:bg-primary-800 rounded-xl shadow-2xl w-full max-w-6xl h-[90vh] min-h-[90vh] max-h-[90vh] flex flex-col overflow-hidden">
        {/* Header */}
        <ModalHeader summary={summary} onClose={onClose} />

        {/* Summary Strip */}
        {summary && <SummaryStrip summary={summary} />}

        {/* Guest Navigation Tabs */}
        {hasMultiple && (
          <GuestTabs
            results={results}
            activeIndex={activeIndex}
            onSelect={setActiveIndex}
          />
        )}

        {/* Comparison Body - flex-1 to fill remaining space, min-h-0 to allow shrinking */}
        <div className="flex-1 min-h-0 overflow-hidden">
          {activeValidation && <GuestComparisonView validation={activeValidation} />}
        </div>

        {/* Footer */}
        {hasMultiple ? (
          <NavigationFooter
            activeIndex={activeIndex}
            total={results.length}
            onPrevious={() => setActiveIndex((i) => i - 1)}
            onNext={() => setActiveIndex((i) => i + 1)}
            onMarkValid={onMarkValid}
            activeResultId={activeValidation?.result_id ?? undefined}
            onClose={onClose}
          />
        ) : (
          <SimpleFooter
            onMarkValid={onMarkValid}
            activeResultId={activeValidation?.result_id ?? undefined}
            onClose={onClose}
          />
        )}
      </div>
    </div>
  );
}