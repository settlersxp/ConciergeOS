import Card from "./Card";
import PromptTextarea from "./PromptTextarea";

interface PreviewPanelProps {
  before: string;
  after: string;
}

export default function PreviewPanel({ before, after }: PreviewPanelProps) {
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      <Card title="Before (Template)">
        <PromptTextarea
          label="Template"
          value={before}
          rows={10}
          as="div"
        />
      </Card>
      <Card title="After (Resolved)">
        <PromptTextarea
          label="Resolved"
          value={after}
          rows={10}
          as="div"
        />
      </Card>
    </div>
  );
}