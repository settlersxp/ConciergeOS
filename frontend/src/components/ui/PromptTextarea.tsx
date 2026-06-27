import { forwardRef } from "react";
import Textarea from "./Textarea";
import FormField from "./FormField";

interface PromptTextareaProps {
  label?: string;
  value: string;
  onChange?: (val: string) => void;
  rows?: number;
  readOnly?: boolean;
  disabled?: boolean;
  placeholder?: string;
  helperText?: string;
  className?: string;
  as?: "textarea" | "div";
}

const PromptTextarea = forwardRef<HTMLTextAreaElement, PromptTextareaProps>(
  (
    {
      label,
      value,
      onChange,
      rows = 6,
      readOnly = false,
      disabled = false,
      placeholder,
      helperText,
      className = "",
      as = "textarea",
    },
    ref
  ) => {
    const baseClasses =
      "w-full rounded-md border border-primary-300 dark:border-primary-600 bg-white dark:bg-primary-900 text-primary-900 dark:text-primary-100 text-sm px-3 py-2 focus:border-secondary-400 focus:outline-none focus:ring-2 focus:ring-secondary-400/20 resize-y";
    const previewClasses =
      "bg-primary-50 dark:bg-primary-950 text-primary-800 dark:text-primary-200 font-mono whitespace-pre-wrap max-h-48 overflow-y-auto";

    const combinedClassName = `${baseClasses} ${
      as === "div" ? previewClasses : ""
    } ${className}`;

    if (as === "div") {
      return (
        <div>
          {label && (
            <label className="block text-sm font-medium text-primary-700 dark:text-primary-300 mb-1">
              {label}
            </label>
          )}
          <div className={combinedClassName} role="textbox" aria-readonly="true">
            {value || "—"}
          </div>
          {helperText && (
            <p className="mt-1 text-xs text-primary-500 dark:text-primary-400">
              {helperText}
            </p>
          )}
        </div>
      );
    }

    const handleChange = onChange
      ? (e: React.ChangeEvent<HTMLTextAreaElement>) => onChange(e.target.value)
      : undefined;

    return (
      <FormField label={label} helperText={helperText}>
        <Textarea
          ref={ref as React.RefCallback<HTMLTextAreaElement> | undefined}
          rows={rows}
          readOnly={readOnly}
          disabled={disabled}
          placeholder={placeholder}
          className={combinedClassName}
          onChange={handleChange}
          value={value}
        />
      </FormField>
    );
  }
);

PromptTextarea.displayName = "PromptTextarea";

export default PromptTextarea;