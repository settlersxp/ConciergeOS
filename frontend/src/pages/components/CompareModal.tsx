import { useEffect, useRef, useCallback } from "react";
import type { TestResult } from "../../types";
import { computeLineDiff } from "../../utils/diff";

interface CompareModalProps {
  resultA: TestResult;
  resultB: TestResult;
  onClose: () => void;
  onToggleValid: (id: number, valid: boolean) => void;
}

function getElapsed(row: TestResult): string {
  const sent = new Date(row.request_sent_time);
  const received = new Date(row.response_received_time);
  return ((received.getTime() - sent.getTime()) / 1000).toFixed(2);
}

function ValidToggle({
  result,
  onToggle,
}: {
  result: TestResult;
  onToggle: (id: number, valid: boolean) => void;
}) {
  const val = result.valid_response;
  const isChecked = val ?? false;
  const isUnset = val === null || val === undefined;

  const labelClass = isUnset
    ? "text-primary-400"
    : isChecked
      ? "text-secondary-500 dark:text-secondary-400"
      : "text-accent-600 dark:text-accent-400";
  const labelText = isUnset ? "Not set" : isChecked ? "Valid" : "Invalid";

  return (
    <div className="flex items-center gap-2">
      <span className={`text-xs font-semibold ${labelClass}`}>{labelText}</span>
      <label className="relative inline-flex items-center cursor-pointer">
        <input
          type="checkbox"
          className="sr-only peer"
          checked={isChecked}
          onChange={(e) => onToggle(result.id, e.target.checked)}
        />
        <div className="w-9 h-5 bg-surface-300 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-secondary-200 dark:bg-primary-600 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-surface-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-secondary-400"></div>
      </label>
    </div>
  );
}

function MetaInfo({ result }: { result: TestResult }) {
  const elapsed = getElapsed(result);
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-1 text-xs">
      <span className="text-primary-500">Batch:</span>
      <span className="font-medium">{result.batch_type}</span>
      <span className="text-primary-500">Model:</span>
      <span className="font-medium">{result.model_name || "—"}</span>
      <span className="text-primary-500">Elapsed:</span>
      <span className="font-medium">{elapsed}s</span>
      <span className="text-primary-500">Length:</span>
      <span className="font-medium">
        {result.response_length ?? "—"}
      </span>
      <span className="text-primary-500">Format:</span>
      <span className="font-medium">{result.response_format || "—"}</span>
      <span className="text-primary-500">JSON:</span>
      <span className="font-medium">
        {result.json_malformed === true
          ? "Malformed"
          : result.json_malformed === false
            ? "OK"
            : "—"}
      </span>
    </div>
  );
}

export default function CompareModal({
  resultA,
  resultB,
  onClose,
  onToggleValid,
}: CompareModalProps) {
  const scrollARef = useRef<HTMLDivElement>(null);
  const scrollBRef = useRef<HTMLDivElement>(null);

  const contentA = resultA.response_content || "(no response content)";
  const contentB = resultB.response_content || "(no response content)";
  const diffed = computeLineDiff(contentA, contentB);

  // Wheel-driven scroll sync (prevent default to avoid momentum races)
  const handleWheel = useCallback(
    (e: WheelEvent) => {
      e.preventDefault();
      const a = scrollARef.current;
      const b = scrollBRef.current;
      if (!a || !b) return;

      const delta =
        Math.abs(e.deltaY) > Math.abs(e.deltaX) ? e.deltaY : e.deltaX;

      a.scrollTop = Math.max(0, a.scrollTop + delta);
      b.scrollTop = Math.max(0, b.scrollTop + delta);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  useEffect(() => {
    const a = scrollARef.current;
    const b = scrollBRef.current;
    if (!a || !b) return;

    a.addEventListener("wheel", handleWheel, { passive: false });
    b.addEventListener("wheel", handleWheel, { passive: false });

    // Reset scroll positions
    a.scrollTop = 0;
    b.scrollTop = 0;

    return () => {
      a.removeEventListener("wheel", handleWheel);
      b.removeEventListener("wheel", handleWheel);
    };
  }, [handleWheel]);

  // Trap focus and handle Escape
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [onClose]);

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
          <h3 className="text-lg font-bold text-primary-900 dark:text-white">
            Side-by-Side Comparison
          </h3>
          <button
            onClick={onClose}
            className="text-primary-400 hover:text-primary-600 dark:hover:text-primary-200 text-2xl leading-none"
          >
            &times;
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="flex-1 grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-surface-200 dark:divide-primary-700 min-h-0">
            {/* Panel A */}
            <div className="flex flex-col min-h-0">
              <div className="px-4 py-3 border-b border-surface-100 dark:border-primary-700 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-sm text-primary-700 dark:text-primary-300">
                    Response A
                  </span>
                  <ValidToggle
                    result={resultA}
                    onToggle={onToggleValid}
                  />
                </div>
                <MetaInfo result={resultA} />
              </div>
              <div
                ref={scrollARef}
                className="flex-1 overflow-auto p-4 text-xs font-mono leading-relaxed"
                style={{ minHeight: 0 }}
              >
                <pre
                  className="compare-diff-pre whitespace-pre-wrap break-words"
                  dangerouslySetInnerHTML={{ __html: diffed.left }}
                />
              </div>
            </div>

            {/* Panel B */}
            <div className="flex flex-col min-h-0">
              <div className="px-4 py-3 border-b border-surface-100 dark:border-primary-700 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-sm text-primary-700 dark:text-primary-300">
                    Response B
                  </span>
                  <ValidToggle
                    result={resultB}
                    onToggle={onToggleValid}
                  />
                </div>
                <MetaInfo result={resultB} />
              </div>
              <div
                ref={scrollBRef}
                className="flex-1 overflow-auto p-4 text-xs font-mono leading-relaxed"
                style={{ minHeight: 0 }}
              >
                <pre
                  className="compare-diff-pre whitespace-pre-wrap break-words"
                  dangerouslySetInnerHTML={{ __html: diffed.right }}
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}