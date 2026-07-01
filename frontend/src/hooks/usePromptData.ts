import { useState, useEffect, useCallback, useRef } from "react";
import { listAllPrompts, listVersions, getByVersion } from "../services/promptsApi";
import type { PromptSummary, PromptVersion } from "../types/prompt";

export interface UsePromptDataOptions {
  showPreview?: boolean;
  onUserPromptChange?: (userPrompt: string) => void;
  refetchRef?: { current?: () => void };
  /** When the user has explicitly overridden the model, use this instead of the version's stored model */
  pendingModel?: number | null | undefined;
}

export interface UsePromptDataResult {
  allPrompts: PromptSummary[];
  versions: PromptVersion[];
  selectedPromptId: string;
  selectedVersion: number | undefined;
  loading: boolean;
  error: string | null;
  resolvedPreview: { system: string; user: string } | null;
  handlePromptIdChange: (e: React.ChangeEvent<HTMLSelectElement>) => void;
  handleVersionChange: (e: React.ChangeEvent<HTMLSelectElement>) => void;
  setSelectedPromptId: (id: string) => void;
}

export default function usePromptData(
  initialPromptId: string,
  initialVersion: number | undefined,
  onChange: (value: { prompt_id: string; version?: number; model_id?: number | null }) => void,
  options: UsePromptDataOptions = {}
): UsePromptDataResult {
  const { showPreview = false, onUserPromptChange, refetchRef, pendingModel } = options;

  const [allPrompts, setAllPrompts] = useState<PromptSummary[]>([]);
  const [selectedPromptId, setSelectedPromptId] = useState(initialPromptId);
  const [selectedVersion, setSelectedVersion] = useState<number | undefined>(initialVersion);
  const [versions, setVersions] = useState<PromptVersion[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resolvedPreview, setResolvedPreview] = useState<{ system: string; user: string } | null>(null);
  const userSelectedVersionRef = useRef<number | undefined>(undefined);

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Track if we should override model from pendingModel in this fetch cycle
  const [overrideModel, setOverrideModel] = useState<number | null | undefined>(undefined);

  // Fetch versions when selectedPromptId changes
  useEffect(() => {
    // Reset the override when the prompt changes
    setOverrideModel(undefined);
    if (selectedPromptId) {
      fetchVersions(selectedPromptId, initialVersion);
    } else {
      setVersions([]);
      setSelectedVersion(undefined);
      userSelectedVersionRef.current = undefined;
      setResolvedPreview(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedPromptId]);

  const resolveAndSetPreview = useCallback(async (promptId: string, version: number) => {
    if (!showPreview) return;
    try {
      const versionData = await getByVersion(promptId, version);
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
  }, [showPreview, onUserPromptChange]);

  const fetchVersions = useCallback(async (promptId: string, explicitVersion?: number) => {
    setLoading(true);
    setError(null);
    try {
      const versionsList = await listVersions(promptId);
      setVersions(versionsList);

      // Determine which version to select using priority order:
      // 1. explicitVersion parameter (from handleVersionChange)
      // 2. userSelectedVersionRef (user clicked a version)
      // 3. initialVersion prop (from parent on mount)
      // 4. highest version (default)
      let targetVersion: number | undefined;

      if (explicitVersion !== undefined) {
        targetVersion = explicitVersion;
        userSelectedVersionRef.current = explicitVersion;
        if (!versionsList.find((v) => v.version === targetVersion)) {
          const sorted = [...versionsList].sort((a, b) => b.version - a.version);
          targetVersion = sorted[0]?.version;
          userSelectedVersionRef.current = targetVersion;
        }
      } else if (userSelectedVersionRef.current !== undefined) {
        targetVersion = userSelectedVersionRef.current;
        if (!versionsList.find((v) => v.version === targetVersion)) {
          const sorted = [...versionsList].sort((a, b) => b.version - a.version);
          targetVersion = sorted[0]?.version;
          userSelectedVersionRef.current = targetVersion;
        }
      } else if (initialVersion !== undefined) {
        targetVersion = initialVersion;
        userSelectedVersionRef.current = initialVersion;
        if (!versionsList.find((v) => v.version === targetVersion)) {
          const sorted = [...versionsList].sort((a, b) => b.version - a.version);
          targetVersion = sorted[0]?.version;
          userSelectedVersionRef.current = targetVersion;
        }
      } else {
        const sorted = [...versionsList].sort((a, b) => b.version - a.version);
        targetVersion = sorted[0]?.version;
      }

      if (targetVersion) {
        setSelectedVersion(targetVersion);
        // Find the model_id for the selected version
        const targetVersionObj = versionsList.find((v) => v.version === targetVersion);
        // Use overrideModel (user's explicit selection) if set, then fall back to pendingModel, then version's stored model
        const modelId = overrideModel !== undefined ? overrideModel : (pendingModel !== undefined ? pendingModel : (targetVersionObj?.model_id ?? null));
        onChange({ prompt_id: promptId, version: targetVersion, model_id: modelId });

        if (showPreview) {
          await resolveAndSetPreview(promptId, targetVersion);
        }
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onChange, showPreview, initialVersion, pendingModel, overrideModel]);

  // Expose refetch callback to parent
  useEffect(() => {
    if (refetchRef) {
      refetchRef.current = async () => {
        if (selectedPromptId) {
          try {
            const versionsList = await listVersions(selectedPromptId);
            const sorted = [...versionsList].sort((a: { version: number }, b: { version: number }) => b.version - a.version);
            const highestVersion = sorted[0]?.version;
            if (highestVersion !== undefined) {
              fetchVersions(selectedPromptId, highestVersion);
            }
          } catch {
            // Ignore refetch errors
          }
        }
      };
    }
  }, [refetchRef, selectedPromptId, fetchVersions]);

  const handlePromptIdChange = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
    const newPromptId = e.target.value;
    setSelectedPromptId(newPromptId);
    setSelectedVersion(undefined);
    userSelectedVersionRef.current = undefined;
    setVersions([]);
    setResolvedPreview(null);
    onChange({ prompt_id: newPromptId, model_id: null });
    fetchVersions(newPromptId);
  }, [fetchVersions, onChange]);

  const handleVersionChange = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
    const v = e.target.value ? Number(e.target.value) : undefined;
    setSelectedVersion(v);
    userSelectedVersionRef.current = v;
    setResolvedPreview(null);
    if (selectedPromptId) {
      const versionObj = versions.find((ver) => ver.version === v);
      // Use overrideModel first, then pendingModel, then version's stored model
      const modelId = overrideModel !== undefined ? overrideModel : (pendingModel !== undefined ? pendingModel : (versionObj?.model_id ?? null));
      onChange({ prompt_id: selectedPromptId, version: v, model_id: modelId });

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
  }, [selectedPromptId, onChange, showPreview, onUserPromptChange, versions, pendingModel]);

  return {
    allPrompts,
    versions,
    selectedPromptId,
    selectedVersion,
    loading,
    error,
    resolvedPreview,
    handlePromptIdChange,
    handleVersionChange,
    setSelectedPromptId,
  };
}