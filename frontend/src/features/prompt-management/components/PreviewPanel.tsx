import Card from "./Card";
import PromptTextarea from "./PromptTextarea";

interface PreviewPanelProps {
  before: string;
  after: string;
  afterUser?: string;
}

export default function PreviewPanel({ before, after, afterUser }: PreviewPanelProps) {
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
      <div className="space-y-4">
        <Card title="After (Resolved) — System">
          <PromptTextarea
            label="Resolved System Prompt"
            value={after}
            rows={10}
            as="div"
          />
        </Card>
        {afterUser && (
          <Card title="After (Resolved) — User">
            <PromptTextarea
              label="Resolved User Prompt"
              value={afterUser}
              rows={6}
              as="div"
            />
          </Card>
        )}
      </div>
    </div>
  );
}
