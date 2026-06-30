import usePromptData from "../../hooks/usePromptData";
import PromptSettingsPanel from "./PromptSettingsPanel";

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
  label,
  showPreview,
  refetchRef,
}: PromptSelectorProps) {
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
    { showPreview, onUserPromptChange, refetchRef }
  );

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
    />
  );
}
