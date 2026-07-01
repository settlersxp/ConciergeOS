import { useEffect, useState } from "react";
import { modelsApi } from "../../services/api";
import usePromptData from "../../hooks/usePromptData";
import type { LLMModel } from "../../types";
import PromptSettingsPanel from "./PromptSettingsPanel";

interface PromptSelectorProps {
  value?: { prompt_id: string; version?: number; model_id?: number | null };
  onChange: (value: { prompt_id: string; version?: number; model_id?: number | null }) => void;
  onUserPromptChange?: (userPrompt: string) => void;
  label?: string;
  showPreview?: boolean;
  refetchRef?: { current?: () => void };
}

export default function PromptSelector({
  value,
  onChange,
  onUserPromptChange,
  label,
  showPreview,
  refetchRef,
}: PromptSelectorProps) {
  const [models, setModels] = useState<LLMModel[]>([]);

  useEffect(() => {
    modelsApi.getAll().then(setModels).catch(() => {});
  }, []);

  const {
    allPrompts,
    versions,
    selectedPromptId,
    selectedVersion,
    loading,
    error,
    resolvedPreview,
    handlePromptIdChange,
    handleVersionChange,
  } = usePromptData(
    value?.prompt_id ?? "",
    value?.version,
    onChange,
    { showPreview, onUserPromptChange, refetchRef, pendingModel: value?.model_id }
  );

  // Use value?.model_id (user's explicit selection from ModelManager) when present,
  // otherwise fall back to the version's stored model_id (which the hook already respects via pendingModel).
  const currentVersion = versions.find(v => v.version === selectedVersion);
  const modelId = value?.model_id ?? (currentVersion?.model_id ?? null);

  const handleModelChange = (newModelId: number | null) => {
    onChange({ prompt_id: selectedPromptId, version: selectedVersion, model_id: newModelId });
  };

  return (
    <PromptSettingsPanel
      allPrompts={allPrompts}
      versions={versions}
      selectedPromptId={selectedPromptId}
      selectedVersion={selectedVersion}
      loading={loading}
      error={error}
      resolvedPreview={resolvedPreview}
      showPreview={showPreview}
      label={label}
      onPromptIdChange={handlePromptIdChange}
      onVersionChange={handleVersionChange}
      models={models}
      modelId={modelId}
      onModelChange={handleModelChange}
    />
  );
}
