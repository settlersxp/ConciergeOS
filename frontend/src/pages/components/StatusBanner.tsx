import type { StatusType } from "../../types";

interface StatusBannerProps {
  message: string;
  type: StatusType;
}

const styleMap: Record<StatusType, { bg: string; text: string; border: string }> = {
  running: {
    bg: "bg-surface-100 dark:bg-primary-900/30",
    text: "text-primary-800 dark:text-primary-200",
    border: "border-surface-300 dark:border-primary-700",
  },
  success: {
    bg: "bg-secondary-50 dark:bg-secondary-900/20",
    text: "text-secondary-600 dark:text-secondary-200",
    border: "border-secondary-300 dark:border-secondary-700",
  },
  error: {
    bg: "bg-accent-50 dark:bg-accent-900/20",
    text: "text-accent-800 dark:text-accent-200",
    border: "border-accent-300 dark:border-accent-700",
  },
};

export default function StatusBanner({ message, type }: StatusBannerProps) {
  const style = styleMap[type];

  return (
    <div
      className={`flex items-center gap-2 px-4 py-3 mb-4 rounded-lg border ${style.bg} ${style.text} ${style.border} text-sm font-medium transition-colors`}
      role="alert"
    >
      {type === "running" && (
        <svg
          className="animate-spin h-4 w-4"
          viewBox="0 0 24 24"
          fill="none"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
          />
        </svg>
      )}
      {type === "success" && (
        <svg
          className="h-4 w-4 shrink-0"
          fill="currentColor"
          viewBox="0 0 20 20"
        >
          <path
            fillRule="evenodd"
            d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
            clipRule="evenodd"
          />
        </svg>
      )}
      {type === "error" && (
        <svg
          className="h-4 w-4 shrink-0"
          fill="currentColor"
          viewBox="0 0 20 20"
        >
          <path
            fillRule="evenodd"
            d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
            clipRule="evenodd"
          />
        </svg>
      )}
      <span>{message}</span>
    </div>
  );
}