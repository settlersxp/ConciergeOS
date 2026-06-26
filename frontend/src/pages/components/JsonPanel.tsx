interface JsonPanelProps {
  title: string;
  content: string | null;
}

function formatJson(raw: string | null): string {
  if (!raw) return "(no data)";
  try {
    return JSON.stringify(JSON.parse(raw), null, 2);
  } catch {
    return raw;
  }
}

export function JsonPanel({ title, content }: JsonPanelProps) {
  return (
    <div className="flex flex-col min-w-0 flex-1">
      {/* Panel Header */}
      <div className="px-4 py-2 border-b border-surface-100 dark:border-primary-700/50 bg-surface-50 dark:bg-primary-800/50 flex-shrink-0">
        <span className="text-xs font-semibold text-primary-600 dark:text-primary-400 uppercase tracking-wider">
          {title}
        </span>
      </div>
      {/* Scrollable Content */}
      <div className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden p-4 text-sm font-mono leading-loose text-primary-900 dark:text-white">
        <pre className="whitespace-pre-wrap break-words">
          {formatJson(content)}
        </pre>
      </div>
    </div>
  );
}