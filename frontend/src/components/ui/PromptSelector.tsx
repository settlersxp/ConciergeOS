import { useState, useEffect, useCallback } from "react";
import { Card, Select, PromptTextarea } from "../../components/ui";
import { listAllPrompts, listVersions, getByVersion } from "../../services/promptsApi";
import type { PromptSummary, PromptVersion } from "../../types/prompt";

interface PromptSelectorProps {
  value?: { prompt_id: string; version?: number };
  onChange: (value: { prompt_id: string; version?: number }) => void;
  onUserPromptChange?: (userPrompt: string) => void;
  label?: string;
  showPreview?: boolean;
  refetchRef?: { current?: () => void };
}

export default function PromptSelector({
  value,
  onChange,
  onUserPromptChange,
  label = "Prompt",
  showPreview = false,
  refetchRef,
}: PromptSelectorProps) {
  const [allPrompts, setAllPrompts] = useState<PromptSummary[]>([]);
  const [selectedPromptId, setSelectedPromptId] = useState(value?.prompt_id ?? "");
  const [selectedVersion, setSelectedVersion] = useState<number | undefined>(value?.version);
  const [versions, setVersions] = useState<PromptVersion[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resolvedPreview, setResolvedPreview] = useState<{ system: string; user: string } | null>(null);

  // Load all prompts on mount
  useEffect(() => {
    listAllPrompts()
      .then((data) => {
        setAllPrompts(data);
        if (data.length > 0 && !selectedPromptId) {
          setSelectedPromptId(data[0].prompt_id);
        }
      })
      .catch(() => setError("Failed to load prompts"));
  }, []);

  // Fetch versions when selectedPromptId changes
  useEffect(() => {
    if (selectedPromptId) {
      fetchVersions(selectedPromptId);
    } else {
      setVersions([]);
      setSelectedVersion(undefined);
      setResolvedPreview(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedPromptId]);

  const fetchVersions = useCallback(async (promptId: string, version?: number) => {
    setLoading(true);
    setError(null);
    try {
      const versionsList = await listVersions(promptId);
      setVersions(versionsList);

      // If no specific version selected, default to the highest version
      let targetVersion = version;
      if (targetVersion === undefined || !versionsList.find((v) => v.version === targetVersion)) {
        const sorted = [...versionsList].sort((a, b) => b.version - a.version);
        targetVersion = sorted[0]?.version;
      }

      if (targetVersion) {
        setSelectedVersion(targetVersion);
        onChange({ prompt_id: promptId, version: targetVersion });

        // Fetch resolved preview if enabled
        if (showPreview) {
          try {
            const versionData = await getByVersion(promptId, targetVersion);
            const systemPrompt = [
              versionData.intention,
              versionData.restrictions,
              versionData.output_structure,
            ]
              .filter(Boolean)
              .join("\n\n");
            setResolvedPreview({
              system: systemPrompt,
              user: versionData.user_prompt_template || "",
            });
            if (onUserPromptChange) {
              onUserPromptChange(versionData.user_prompt_template || "");
            }
          } catch {
            // Ignore preview fetch errors
          }
        }
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [onChange, showPreview]);

  // Expose refetch callback to parent for manual triggers (e.g., after set default)
  useEffect(() => {
    if (refetchRef) {
      refetchRef.current = () => {
        if (selectedPromptId) {
          fetchVersions(selectedPromptId, selectedVersion);
        }
      };
    }
  }, [refetchRef, selectedPromptId, selectedVersion, fetchVersions]);

  // Sync with external value prop changes (e.g., after creating a new version)
  useEffect(() => {
    if (value?.prompt_id && value.prompt_id !== selectedPromptId) {
      // Prompt changed externally
      setSelectedPromptId(value.prompt_id);
      fetchVersions(value.prompt_id, value.version);
    } else if (value?.version !== undefined && value.version !== selectedVersion) {
      // Version changed externally (e.g., after creating a new version)
      fetchVersions(selectedPromptId, value.version);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value?.prompt_id, value?.version]);

  const handlePromptIdChange = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
    const newPromptId = e.target.value;
    setSelectedPromptId(newPromptId);
    setSelectedVersion(undefined);
    setVersions([]);
    setResolvedPreview(null);
    fetchVersions(newPromptId, undefined);
  }, [fetchVersions]);

  const handleVersionChange = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
    const v = e.target.value ? Number(e.target.value) : undefined;
    setSelectedVersion(v);
    setResolvedPreview(null);
    if (selectedPromptId) {
      onChange({ prompt_id: selectedPromptId, version: v });

      // Fetch resolved preview if enabled
      if (showPreview && v) {
        getByVersion(selectedPromptId, v)
          .then((versionData) => {
            const systemPrompt = [
              versionData.intention,
              versionData.restrictions,
              versionData.output_structure,
            ]
              .filter(Boolean)
              .join("\n\n");
            setResolvedPreview({
              system: systemPrompt,
              user: versionData.user_prompt_template || "",
            });
            if (onUserPromptChange) {
              onUserPromptChange(versionData.user_prompt_template || "");
            }
          })
          .catch(() => {});
      }
    }
  }, [selectedPromptId, onChange, showPreview]);

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
              onChange={handlePromptIdChange}
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
              onChange={handleVersionChange}
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