import PromptTextarea from "./PromptTextarea";
import Button from "./Button";

interface PromptEditorSectionProps {
  label: string;
  value: string;
  onChange: (val: string) => void;
  onImprove?: () => void;
  onClone?: () => void;
}

export default function PromptEditorSection({
  label,
  value,
  onChange,
  onImprove,
  onClone,
}: PromptEditorSectionProps) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1">
        <PromptTextarea
          label={label}
          value={value}
          onChange={onChange}
          rows={4}
        />
      </div>
      <div className="flex flex-col gap-1">
        {onImprove && (
          <Button
            onClick={onImprove}
            size="sm"
            variant="ghost"
            className="border border-surface-300 dark:border-primary-600 whitespace-nowrap"
          >
            Improve with AI
          </Button>
        )}
        {onClone && (
          <Button
            onClick={onClone}
            size="sm"
            variant="ghost"
            className="border border-surface-300 dark:border-primary-600 whitespace-nowrap"
          >
            Clone
          </Button>
        )}
      </div>
    </div>
  );
}
