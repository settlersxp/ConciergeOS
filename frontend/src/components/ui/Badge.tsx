import type { ReactNode } from "react";

type BadgeVariant = "success" | "warning" | "danger" | "neutral" | "info";

interface BadgeProps {
  variant?: BadgeVariant;
  children: ReactNode;
  className?: string;
}

const variantClasses: Record<BadgeVariant, string> = {
  success:
    "bg-secondary-100 text-secondary-600 dark:bg-secondary-900/30 dark:text-secondary-400",
  warning:
    "bg-surface-200 text-surface-600 dark:bg-surface-900/30 dark:text-surface-400",
  danger:
    "bg-accent-100 text-accent-600 dark:bg-accent-900/30 dark:text-accent-400",
  neutral:
    "bg-primary-100 text-primary-600 dark:bg-primary-900/30 dark:text-primary-400",
  info:
    "bg-primary-100 text-primary-600 dark:bg-primary-900/30 dark:text-primary-400",
};

export default function Badge({
  variant = "neutral",
  children,
  className = "",
}: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${variantClasses[variant]} ${className}`}
    >
      {children}
    </span>
  );
}