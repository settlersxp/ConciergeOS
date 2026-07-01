import Card from "./Card";
import Select from "./Select";
import PromptTextarea from "./PromptTextarea";
import type { PromptSummary, PromptVersion } from "../../types/prompt";
import type { LLMModel } from "../../types";

interface PromptSettingsPanelProps {
  allPrompts: PromptSummary[];
  versions: PromptVersion[];
  selectedPromptId: string;
  selectedVersion: number | undefined;
  loading: boolean;
  error: string | null;
  resolvedPreview: { system: string; user: string } | null;
  showPreview?: boolean;
  label?: string;
  onPromptIdChange: (e: React.ChangeEvent<HTMLSelectElement>) => void;
  onVersionChange: (e: React.ChangeEvent<HTMLSelectElement>) => void;
  /** All configured LLM models for the model selector */
  models?: LLMModel[];
  /** Current model_id for the selected prompt version (null = default) */
  modelId?: number | null;
  /** Called when model selection changes */
  onModelChange?: (modelId: number | null) => void;
}

export default function PromptSettingsPanel({
  allPrompts,
  versions,
  selectedPromptId,
  selectedVersion,
  loading,
  error,
  resolvedPreview,
  showPreview,
  label,
  onPromptIdChange,
  onVersionChange,
  models,
  modelId,
  onModelChange,
}: PromptSettingsPanelProps) {
  return (
    <Card title={label ?? "Prompt Settings"}>
      <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
        <div>
          <label className="block text-sm font-medium text-primary-700 dark:text-primary-300 mb-1">
            Prompt
          </label>
          <Select value={selectedPromptId} onChange={onPromptIdChange}>
            <option value="">-- Select Prompt --</option>
            {allPrompts.map((p: PromptSummary) => (
              <option key={p.prompt_id} value={p.prompt_id}>
                {p.prompt_id} ({p.version_count} version{p.version_count !== 1 ? "s" : ""})
              </option>
            ))}
          </Select>
        </div>

        <div>
          <label className="block text-sm font-medium text-primary-700 dark:text-primary-300 mb-1">
            Version
          </label>
          <Select
            value={selectedVersion ?? ""}
            onChange={onVersionChange}
            disabled={loading || !selectedPromptId || versions.length === 0}
          >
            <option value="">
              {!selectedPromptId
                ? "Select a prompt first"
                : versions.length === 0
                  ? "No versions available"
                  : "Select a version"}
            </option>
            {versions.map((v: PromptVersion) => (
              <option key={v.version} value={v.version}>
                v{v.version}
                {v.is_default ? " (default)" : ""}
              </option>
            ))}
          </Select>
        </div>
      </div>

      {/* LLM Model Selector */}
      {models && models.length > 0 && (
        <div className="mt-4">
          <label className="block text-sm font-medium text-primary-700 dark:text-primary-300 mb-1">
            LLM Model
          </label>
          <Select
            value={String(modelId ?? "")}
            onChange={(e) => {
              const id = e.target.value ? Number(e.target.value) : null;
              onModelChange?.(id);
            }}
          >
            <option value="">Default (system model)</option>
            {models.map((m) => (
              <option key={m.model_id} value={m.model_id}>
                {m.name} ({m.model_name}) — {m.model_type.replace("_", " ")}
              </option>
            ))}
          </Select>
          <p className="mt-1 text-xs text-primary-400 dark:text-primary-500">
            Assign an LLM model to this prompt version. Leave empty to use the default.
          </p>
        </div>
      )}

      {/* Error display */}
      {error && (
        <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
      )}

      {/* Loading indicator */}
      {loading && (
        <p className="text-sm text-primary-600 dark:text-primary-400">
          Loading prompt...
        </p>
      )}

      {/* Preview Resolved Prompts */}
      {showPreview && resolvedPreview && (
        <details className="group mt-2">
          <summary className="cursor-pointer text-sm font-medium text-primary-700 dark:text-primary-300 group-open:font-bold">
            Preview Resolved Prompts
          </summary>
          <div className="mt-2 space-y-3">
            <PromptTextarea
              label="System Prompt (resolved)"
              value={resolvedPreview.system}
              rows={6}
              as="div"
            />
            <PromptTextarea
              label="User Prompt Template (resolved)"
              value={resolvedPreview.user}
              rows={6}
              as="div"
            />
          </div>
        </details>
      )}
    </Card>
  );
}