import { useEffect, useState } from "react";
import { Select, FormField } from "../../components/ui";
import { listVersions } from "../../services/promptsApi";
import type { PromptVersion } from "../../types/prompt";

interface PromptSelectorProps {
  promptId: string;
  value?: { prompt_id: string; version?: number };
  onChange: (value: { prompt_id: string; version?: number }) => void;
  label?: string;
}

export default function PromptSelector({
  promptId,
  value,
  onChange,
  label = "Prompt",
}: PromptSelectorProps) {
  const [versions, setVersions] = useState<PromptVersion[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    listVersions(promptId)
      .then(setVersions)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [promptId]);

  const selectedVersion = value?.version;

  return (
    <FormField
      htmlFor={`promptSelector-${promptId}`}
      label={label}
      helperText={error || undefined}
    >
      <Select
        id={`promptSelector-${promptId}`}
        value={selectedVersion ?? ""}
        onChange={(e) => {
          const v = e.target.value;
          onChange({ prompt_id: promptId, version: v ? Number(v) : undefined });
        }}
        disabled={loading}
      >
        {loading ? (
          <option value="">Loading...</option>
        ) : error ? (
          <option value="">Error loading prompts</option>
        ) : versions.length === 0 ? (
          <option value="">No prompts available</option>
        ) : (
          versions.map((p) => (
            <option key={p.id} value={p.version}>
              v{p.version} — {p.name}
              {p.is_default ? " (default)" : ""}
            </option>
          ))
        )}
      </Select>
    </FormField>
  );
}