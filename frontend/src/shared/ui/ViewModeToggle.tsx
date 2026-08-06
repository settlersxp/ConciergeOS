interface ViewModeToggleProps<T extends string> {
  modes: { key: T; label: string }[];
  activeMode: T;
  onChange: (mode: T) => void;
}

export default function ViewModeToggle<T extends string>({
  modes,
  activeMode,
  onChange,
}: ViewModeToggleProps<T>) {
  return (
    <div className="flex rounded-lg border border-surface-200 dark:border-primary-800 overflow-hidden">
      {modes.map((mode) => (
        <button
          key={mode.key}
          onClick={() => onChange(mode.key)}
          className={`px-4 py-1.5 text-sm font-medium transition-colors ${
            activeMode === mode.key
              ? "bg-primary-600 text-white"
              : "bg-surface-50 text-primary-600 hover:bg-surface-100 dark:bg-primary-900/30 dark:text-primary-400 dark:hover:bg-primary-900/50"
          }`}
        >
          {mode.label}
        </button>
      ))}
    </div>
  );
}