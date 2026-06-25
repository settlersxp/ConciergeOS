import type { ReactNode } from "react";

type ButtonVariant = "primary" | "secondary" | "danger" | "success" | "accent" | "ghost";
type ButtonSize = "sm" | "md" | "lg";

interface ButtonProps {
  variant?: ButtonVariant;
  size?: ButtonSize;
  disabled?: boolean;
  loading?: boolean;
  children: ReactNode;
  onClick?: () => void;
  type?: "button" | "submit" | "reset";
  className?: string;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    "bg-secondary-400 text-white hover:bg-secondary-500 disabled:bg-secondary-300",
  secondary:
    "bg-surface-200 text-primary-700 hover:bg-surface-300 dark:bg-primary-700 dark:text-primary-200 dark:hover:bg-primary-600 disabled:bg-surface-100 dark:disabled:bg-primary-800",
  danger:
    "bg-accent-600 text-white hover:bg-accent-700 disabled:bg-accent-400",
  success:
    "bg-green-600 text-white hover:bg-green-700 disabled:bg-green-400",
  accent:
    "bg-accent-400 text-white hover:bg-accent-500 disabled:bg-accent-300",
  ghost:
    "bg-transparent text-primary-700 hover:bg-surface-100 dark:text-primary-300 dark:hover:bg-primary-700",
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: "px-3 py-1.5 text-xs",
  md: "px-4 py-2 text-sm",
  lg: "px-6 py-2.5 text-sm font-medium",
};

export default function Button({
  variant = "primary",
  size = "md",
  disabled = false,
  loading = false,
  children,
  onClick,
  type = "button",
  className = "",
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      onClick={onClick}
      className={`rounded-md ${variantClasses[variant]} ${sizeClasses[size]} transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${className}`}
    >
      {loading ? "Loading..." : children}
    </button>
  );
}