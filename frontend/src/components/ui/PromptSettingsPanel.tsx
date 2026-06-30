import Card from "./Card";
import Select from "./Select";
import PromptTextarea from "./PromptTextarea";
import type { PromptSummary, PromptVersion } from "../../types/prompt";

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
}

export default function PromptSettingsPanel({
  allPrompts,
  versions,
  selectedPromptId,
  selectedVersion,
  loading,
  error,
  resolvedPreview,
  showPreview = false,
  label = "Prompt",
  onPromptIdChange,
  onVersionChange,
}: PromptSettingsPanelProps) {
  return (
    <Card>
      <div className="space-y-4">
        <h3 className="text-lg font-semibold text-primary-900 dark:text-white">
          Prompt Settings
        </h3>

        <div className="grid gap-4 md:grid-cols-2">
          {/* Prompt ID Selector */}
          <div>
            <label className="block text-sm font-medium text-primary-700 dark:text-primary-300 mb-1">
              {label}
            </label>
            <Select
              value={selectedPromptId}
              onChange={onPromptIdChange}
              disabled={loading}
            >
              <option value="">Select a prompt</option>
              {allPrompts.map((p) => (
                <option key={p.prompt_id} value={p.prompt_id}>
                  {p.prompt_id}
                </option>
              ))}
            </Select>
          </div>

          {/* Version Selector */}
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
      </div>
    </Card>
  );
}