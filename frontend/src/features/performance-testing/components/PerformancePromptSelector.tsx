import { PromptSelector } from "../../components/ui";

interface PerformancePromptSelectorProps {
  value?: { prompt_id: string; version?: number };
  onChange: (
    value: { prompt_id: string; version?: number },
    userPrompt: string,
  ) => void;
  label?: string;
}

export default function PerformancePromptSelector({
  value,
  onChange,
  label = "Prompt",
}: PerformancePromptSelectorProps) {
  return (
    <PromptSelector
      value={value}
      onChange={(selection) => onChange(selection, "")}
      onUserPromptChange={(userPrompt) => {
        // Get current value from state
        onChange({ prompt_id: value?.prompt_id ?? "", version: value?.version }, userPrompt);
      }}
      label={label}
      showPreview
    />
  );
}