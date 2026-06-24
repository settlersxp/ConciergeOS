import type { ReactNode } from "react";

interface FormFieldProps {
  label?: string;
  htmlFor?: string;
  helperText?: string;
  prefix?: string;
  children: ReactNode;
  className?: string;
}

export default function FormField({
  label,
  htmlFor,
  helperText,
  prefix,
  children,
  className = "",
}: FormFieldProps) {
  return (
    <div className={className}>
      {label && (
        <label
          htmlFor={htmlFor}
          className="block text-sm font-medium text-primary-700 dark:text-primary-300 mb-1"
        >
          {prefix && (
            <span className="text-primary-400 font-normal mr-1">{prefix}</span>
          )}
          {label}
        </label>
      )}
      {children}
      {helperText && (
        <p className="mt-1 text-xs text-primary-500 dark:text-primary-400">
          {helperText}
        </p>
      )}
    </div>
  );
}