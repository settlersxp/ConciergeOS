import { Card, FormField, Textarea } from "../../components/ui";

interface PromptSettingsCardProps {
  systemPrompt: string;
  userPrompt: string;
  onSystemPromptChange: (v: string) => void;
  onUserPromptChange: (v: string) => void;
}

export default function PromptSettingsCard({
  systemPrompt,
  userPrompt,
  onSystemPromptChange,
  onUserPromptChange,
}: PromptSettingsCardProps) {
  return (
    <Card title="Prompt Settings">
      <div className="mb-4">
        <FormField htmlFor="systemPrompt" label="System Prompt">
          <Textarea
            id="systemPrompt"
            rows={4}
            value={systemPrompt}
            onChange={(e) => onSystemPromptChange(e.target.value)}
          />
        </FormField>
      </div>

      <div className="mb-4">
        <FormField htmlFor="userPrompt" label="User Prompt Template">
          <Textarea
            id="userPrompt"
            rows={6}
            value={userPrompt}
            onChange={(e) => onUserPromptChange(e.target.value)}
          />
        </FormField>
      </div>
    </Card>
  );
}