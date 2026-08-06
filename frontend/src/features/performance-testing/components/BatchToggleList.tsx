import React, { useMemo } from "react";

interface BatchToggleListProps<TItem> {
  items: TItem[];
  enabledItems: Set<string>;
  onToggle: (id: string) => void;
  searchPlaceholder?: string;
  getId: (item: TItem) => string;
  getName: (item: TItem) => string;
  gridColumns?: 1 | 2 | 3;
  renderItem?: (item: TItem) => React.ReactNode;
}

export default function BatchToggleList<TItem>({
  items,
  enabledItems,
  onToggle,
  searchPlaceholder = "Search...",
  getId,
  getName,
  gridColumns = 3,
  renderItem,
}: BatchToggleListProps<TItem>) {
  const [search, setSearch] = React.useState("");

  const gridClass = useMemo(() => {
    switch (gridColumns) {
      case 1:
        return "grid-cols-1";
      case 2:
        return "grid-cols-1 sm:grid-cols-2";
      case 3:
        return "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3";
      default:
        return "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3";
    }
  }, [gridColumns]);

  const filteredItems = useMemo(() => {
    if (!search.trim()) return items;
    const query = search.toLowerCase();
    return items.filter(
      (item) =>
        getId(item).toLowerCase().includes(query) ||
        getName(item).toLowerCase().includes(query)
    );
  }, [items, search, getId, getName]);

  return (
    <div>
      <div className="mb-3">
        <input
          type="text"
          placeholder={searchPlaceholder}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full rounded-md border border-surface-200 bg-surface-50 px-3 py-2 text-sm text-primary-700 placeholder-primary-400 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-primary-800 dark:bg-primary-900/30 dark:text-primary-300 dark:placeholder-primary-600"
        />
      </div>
      <div className={`grid ${gridClass} gap-2 mt-2`}>
        {filteredItems.map((item) => {
          const id = getId(item);
          const name = getName(item);
          const isEnabled = enabledItems.has(id);
          return (
            <label
              key={id}
              className={`flex items-center gap-2 rounded-md px-3 py-2 cursor-pointer transition-colors ${
                isEnabled
                  ? "bg-primary-50 border border-primary-200 dark:bg-primary-900/30 dark:border-primary-700"
                  : "bg-surface-50 border border-surface-200 opacity-50 dark:bg-primary-900/20 dark:border-primary-800"
              }`}
            >
              <input
                type="checkbox"
                checked={isEnabled}
                onChange={() => onToggle(id)}
                className="h-4 w-4 rounded border-surface-300 text-primary-600 focus:ring-primary-500"
              />
              <span className="text-sm text-primary-700 dark:text-primary-300 truncate flex-1">
                {renderItem ? renderItem(item) : name}
              </span>
            </label>
          );
        })}
      </div>
    </div>
  );
}