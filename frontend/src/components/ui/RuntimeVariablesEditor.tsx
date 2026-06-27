import type { ReactNode } from "react";
import { FormField, Input } from "./index";

interface RuntimeVariablesEditorProps {
  /** The key for the runtime variable (e.g. "customer_name") */
  variableKey: string;
  /** The value for the runtime variable (read-only, synced from source field) */
  variableValue: string;
  /** Callback when the key changes */
  onKeyChange: (key: string) => void;
  /** Label for the key input field (default: "Variable Key") */
  keyLabel?: string;
  /** Label for the value input field (default: "Value (synced from Customer Name)") */
  valueLabel?: string;
  /** Placeholder for the key input (default: "e.g. customer_name") */
  keyPlaceholder?: string;
  /** Custom description text or JSX (optional) */
  description?: ReactNode;
}

export default function RuntimeVariablesEditor({
  variableKey,
  variableValue,
  onKeyChange,
  keyLabel = "Variable Key",
  valueLabel = "Value (synced from Customer Name)",
  keyPlaceholder = "e.g. customer_name",
  description,
}: RuntimeVariablesEditorProps) {
  return (
    <div className="mt-6 border-t border-primary-200 dark:border-primary-800 pt-4">
      <h3 className="mb-2 text-sm font-semibold text-primary-700 dark:text-primary-300">
        Runtime Variables (for {"{table.field}"} placeholders)
      </h3>
      <div className="mb-3 text-xs text-primary-600 dark:text-primary-400">
        {description || (
          <>
            Sets the value for placeholders in your prompt template (e.g., {"{customer_name}"}, {"{customers.name}"}).
          </>
        )}
      </div>

      <div className="flex gap-4">
        <FormField label={keyLabel} className="flex-1">
          <Input
            type="text"
            placeholder={keyPlaceholder}
            value={variableKey}
            onChange={(e) => onKeyChange(e.target.value)}
          />
        </FormField>
        <FormField label={valueLabel} className="flex-[2]">
          <Input
            type="text"
            value={variableValue}
            readOnly
            placeholder="—"
          />
        </FormField>
      </div>
    </div>
  );
}