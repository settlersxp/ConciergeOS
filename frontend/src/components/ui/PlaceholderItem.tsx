import { useState } from "react";
import Badge from "./Badge";
import Button from "./Button";
interface Props {
  placeholder: { key: string; description: string; category: string; dynamic: boolean; example: string };
}
export default function PlaceholderItem({ placeholder }: Props) {
  const [showExample, setShowExample] = useState(false);
  const variant = placeholder.category === "schema" ? "info" : placeholder.category === "data" ? "success" : "warning";
  return (
    <div className="rounded-lg border border-surface-200 bg-white p-3 dark:border-primary-700 dark:bg-primary-800">
      <div className="flex items-start justify-between">
        <code className="text-sm font-mono font-semibold text-primary-900 dark:text-primary-100">
          {"{" + placeholder.key + "}"}
        </code>
        <div className="flex items-center gap-2">
          <Badge variant={variant as any}>{placeholder.category}</Badge>
          <Button variant="ghost" size="sm" onClick={() => navigator.clipboard?.writeText("{" + placeholder.key + "}")}>Copy</Button>
        </div>
      </div>
      <p className="mt-1 text-xs text-primary-500 dark:text-primary-400">{placeholder.description}</p>
      {showExample && (
        <div className="mt-2 rounded bg-primary-50 p-2 text-xs font-mono dark:bg-primary-900/50">
          <pre className="whitespace-pre-wrap text-primary-700 dark:text-primary-300">{placeholder.example}</pre>
        </div>
      )}
      <button className="mt-1 text-xs text-secondary-600 dark:text-secondary-400" onClick={() => setShowExample(!showExample)}>
        {showExample ? "Hide" : "Show"} example
      </button>
    </div>
  );
}
