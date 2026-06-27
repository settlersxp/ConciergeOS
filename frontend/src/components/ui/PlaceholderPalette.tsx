import { useState, useEffect } from "react";
import Card from "./Card";
import PlaceholderCategorySection from "./PlaceholderCategorySection";
import { Button, Input } from "./";
import FieldBrowser from "./FieldBrowser";
import type { FieldSchema } from "../../types";

type Item = { key: string; description: string; category: string; dynamic: boolean; example: string };

/** A single key-value row for runtime variables. */
function RuntimeVariableRow({
  varKey,
  value: initialValue,
  onRemove,
  onValueChange,
}: {
  varKey: string;
  value: string;
  onRemove: () => void;
  onValueChange: (v: string) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-600 rounded-md text-xs font-mono text-slate-700 dark:text-slate-300">
        {varKey}
      </div>
      <Input
        value={initialValue}
        onChange={(e) => onValueChange(e.target.value)}
        placeholder="value"
        className="flex-1 text-xs"
      />
      <Button
        variant="ghost"
        onClick={onRemove}
        className="shrink-0 p-1 h-6 w-6 flex items-center justify-center text-slate-400 hover:text-red-500 hover:bg-slate-100 dark:hover:bg-slate-700 rounded"
      >
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
          <path d="M3 3L9 9M9 3L3 9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      </Button>
    </div>
  );
}

/** Detect {key} patterns from a prompt template string. */
function detectVariables(template: string): Set<string> {
  const vars = new Set<string>();
  const regex = /\{([^}]+)\}/g;
  let match;
  while ((match = regex.exec(template)) !== null) {
    const key = match[1].trim();
    // Only include keys that look like table.field (contain a dot)
    // or are known special keys like customers.first_name
    if (key.includes(".") || key.includes("_")) {
      vars.add(key);
    }
  }
  return vars;
}

export default function PlaceholderPalette({
  placeholders,
  userPromptTemplate = "",
  runtimeVariables = {},
  onRuntimeVariablesChange,
}: {
  placeholders: Item[];
  /** Optional user prompt template to auto-detect {table.field} variables. */
  userPromptTemplate?: string;
  /** Current runtime variable key→value mappings. */
  runtimeVariables?: Record<string, string>;
  /** Callback when runtime variables change. */
  onRuntimeVariablesChange?: (vars: Record<string, string>) => void;
}) {
  // Fetch field schema from the backend
  const [fieldSchema, setFieldSchema] = useState<FieldSchema>({});
  const [showFieldBrowser, setShowFieldBrowser] = useState(false);

  useEffect(() => {
    fetch("/api/prompts/field-schema")
      .then((r) => (r.ok ? r.json() : Promise.reject(r.statusText)))
      .then(setFieldSchema)
      .catch(() => {});
  }, []);

  const handleInsertField = (key: string) => {
    const next = { ...runtimeVariables, [key]: "" };
    setVars(next);
    onRuntimeVariablesChange?.(next);
  };

  const groups: Record<string, Item[]> = { schema: [], data: [], context: [] };
  for (const p of placeholders) { if (groups[p.category]) groups[p.category].push(p); }

  // Detect {table.field} variables from the template
  const detectedVars = detectVariables(userPromptTemplate);

  // Build a complete map: detected + user-defined
  const [vars, setVars] = useState<Record<string, string>>(() => {
    const merged: Record<string, string> = { ...runtimeVariables };
    // Ensure detected vars exist with empty defaults
    for (const key of detectedVars) {
      if (!(key in merged)) {
        merged[key] = "";
      }
    }
    return merged;
  });

  // Sync when parent props change
  useEffect(() => {
    const merged: Record<string, string> = { ...runtimeVariables };
    for (const key of detectedVars) {
      if (!(key in merged)) {
        merged[key] = "";
      }
    }
    setVars(merged);
  }, [userPromptTemplate, runtimeVariables]);

  const addVariable = () => {
    const next = { ...vars, "": "" };
    setVars(next);
    onRuntimeVariablesChange?.(next);
  };

  const updateKey = (oldKey: string, newKey: string) => {
    if (oldKey === newKey || !newKey) {
      if (oldKey !== newKey) {
        const next = { ...vars };
        if (oldKey in next) {
          next[newKey] = next[oldKey];
          delete next[oldKey];
        }
        setVars(next);
        onRuntimeVariablesChange?.(next);
      }
      return;
    }
    const next: Record<string, string> = { ...vars };
    const val = next[oldKey];
    delete next[oldKey];
    next[newKey] = val ?? "";
    setVars(next);
    onRuntimeVariablesChange?.(next);
  };

  const updateValue = (key: string, value: string) => {
    const next = { ...vars, [key]: value };
    setVars(next);
    onRuntimeVariablesChange?.(next);
  };

  const removeVariable = (key: string) => {
    const next = { ...vars };
    delete next[key];
    setVars(next);
    onRuntimeVariablesChange?.(next);
  };

  const runtimeVarList = Object.entries(vars).filter(([k]) => k);

  return (
    <div className="space-y-4">
      <Card title="Available Placeholders">
        <div className="space-y-4">
          {groups.schema.length > 0 && <PlaceholderCategorySection title="Schema" items={groups.schema} />}
          {groups.data.length > 0 && <PlaceholderCategorySection title="Data" items={groups.data} />}
          {groups.context.length > 0 && <PlaceholderCategorySection title="Context" items={groups.context} />}
          {Object.values(groups).every((g) => g.length === 0) && <p className="text-sm text-slate-500 dark:text-slate-400">No placeholders.</p>}
        </div>
      </Card>

      {/* Field Browser Modal */}
      {showFieldBrowser && (
        <FieldBrowser
          schema={fieldSchema}
          onInsert={handleInsertField}
          onClose={() => setShowFieldBrowser(false)}
        />
      )}

      <Card title="Runtime Variables">
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
              Variables matching{" "}
            <code className="px-1 py-0.5 bg-slate-100 dark:bg-slate-700 rounded text-xs font-mono text-slate-700 dark:text-slate-300">
              {"{table.field}"}
            </code>{" "}
            or{" "}
            <code className="px-1 py-0.5 bg-slate-100 dark:bg-slate-700 rounded text-xs font-mono text-slate-700 dark:text-slate-300">
              {"{snake_case_key}"}
            </code>{" "}
            detected in the template are listed below. Set their values to resolve placeholders at query-time.
            </div>
            <div title="Browse available database fields">
            <Button
              variant="primary"
              onClick={() => setShowFieldBrowser(true)}
              className="text-sm flex items-center gap-1.5 shrink-0"
            >
              <svg width="14" height="14" viewBox="0 0 12 12" fill="none" className="shrink-0">
                <path d="M1 3h10M1 6h10M1 9h10M4 1v10" stroke="currentColor" strokeWidth="1" strokeLinecap="round" />
              </svg>
              Browse Fields
            </Button>
            </div>
          </div>

          {runtimeVarList.length === 0 ? (
            <div className="text-sm text-slate-500 dark:text-slate-400">
              No runtime variables detected. Add{" "}
              <code className="px-1 py-0.5 bg-slate-100 dark:bg-slate-700 rounded text-xs font-mono text-slate-700 dark:text-slate-300">
                {"{table.field}"}
              </code>{" "}
              patterns to your template to create variables.
            </div>
          ) : (
            <div className="space-y-2">
              {runtimeVarList.map(([key, value]) => (
                <RuntimeVariableRow
                  key={key}
                  varKey={key}
                  value={value}
                  onRemove={() => removeVariable(key)}
                  onValueChange={(v) => updateValue(key, v)}
                />
              ))}
            </div>
          )}

          <Button variant="ghost" onClick={addVariable} className="text-sm">
            <span className="mr-1">+</span> Add Variable
          </Button>
        </div>
      </Card>
    </div>
  );
}
