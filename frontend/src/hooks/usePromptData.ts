import { useState, useEffect, useCallback, useRef } from "react";
import { listAllPrompts, listVersions, getByVersion } from "../services/promptsApi";
import type { PromptSummary, PromptVersion } from "../types/prompt";

export interface UsePromptDataOptions {
  showPreview?: boolean;
  onUserPromptChange?: (userPrompt: string) => void;
  refetchRef?: { current?: () => void };
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
  onChange: (value: { prompt_id: string; version?: number }) => void,
  options: UsePromptDataOptions = {}
): UsePromptDataResult {
  const { showPreview = false, onUserPromptChange, refetchRef } = options;

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

  // Fetch versions when selectedPromptId changes
  useEffect(() => {
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
        onChange({ prompt_id: promptId, version: targetVersion });

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
  }, [onChange, showPreview, initialVersion]);

  // Expose refetch callback to parent
  useEffect(() => {
    if (refetchRef) {
      refetchRef.current = () => {
        if (selectedPromptId) {
          fetchVersions(selectedPromptId);
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
    fetchVersions(newPromptId);
  }, [fetchVersions]);

  const handleVersionChange = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
    const v = e.target.value ? Number(e.target.value) : undefined;
    setSelectedVersion(v);
    userSelectedVersionRef.current = v;
    setResolvedPreview(null);
    if (selectedPromptId) {
      onChange({ prompt_id: selectedPromptId, version: v });

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
  }, [selectedPromptId, onChange, showPreview, onUserPromptChange]);

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