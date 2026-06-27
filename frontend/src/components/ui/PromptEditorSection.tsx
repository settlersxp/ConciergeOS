import PromptTextarea from "./PromptTextarea";

interface PromptEditorSectionProps {
  label: string;
  value: string;
  onChange: (val: string) => void;
}

export default function PromptEditorSection({
  label,
  value,
  onChange,
}: PromptEditorSectionProps) {
  return (
    <PromptTextarea
      label={label}
      value={value}
      onChange={onChange}
      rows={4}
    />
  );
}