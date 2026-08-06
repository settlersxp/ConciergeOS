import type { ReactNode } from "react";

interface CardProps {
  title?: string;
  description?: string;
  children: ReactNode;
  className?: string;
  titleClassName?: string;
}

export default function Card({
  title,
  description,
  children,
  className = "",
  titleClassName = "",
}: CardProps) {
  return (
    <div
      className={`rounded-lg border border-surface-200 bg-surface-50 p-6 shadow-sm dark:border-primary-700 dark:bg-primary-800 ${className}`}
    >
      {(title || description) && (
        <div className="mb-4">
          {title && (
            <h2
              className={`text-lg font-semibold text-primary-900 dark:text-white ${titleClassName}`}
            >
              {title}
            </h2>
          )}
          {description && (
            <p className="mt-1 text-xs text-primary-500 dark:text-primary-400">
              {description}
            </p>
          )}
        </div>
      )}
      {children}
    </div>
  );
}