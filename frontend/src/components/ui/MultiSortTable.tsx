import React from "react";

export interface SortConfig {
  key: string;
  direction: "asc" | "desc";
}

export interface TableColumn<TData> {
  key: string;
  header: string;
  className?: string;
  headerClassName?: string;
  render?: (item: TData) => React.ReactNode;
  cellClassName?: (item: TData, index: number) => string;
}

interface MultiSortTableProps<TData> {
  data: TData[];
  columns: TableColumn<TData>[];
  sortConfig: SortConfig[];
  onSort: (key: string, event?: React.MouseEvent) => void;
  onClearSort?: () => void;
  hasActiveSort?: boolean;
  rowKey?: (item: TData, index: number) => string;
  onRowClick?: (item: TData) => void;
  rowClassName?: (item: TData, index: number) => string;
}

function getSortDirectionIndicator(
  sortConfig: SortConfig[],
  key: string
): string | null {
  const sort = sortConfig.find((s) => s.key === key);
  if (!sort) return null;
  const index = sortConfig.indexOf(sort);
  return `${index + 1}${sort.direction === "asc" ? " ↑" : " ↓"}`;
}

function defaultRowKey<TData>(_item: TData, index: number): string {
  return String(index);
}

export default function MultiSortTable<TData>({
  data,
  columns,
  sortConfig,
  onSort,
  onClearSort,
  hasActiveSort,
  rowKey = defaultRowKey,
  onRowClick,
  rowClassName,
}: MultiSortTableProps<TData>) {
  const sortedData = React.useMemo(() => {
    if (sortConfig.length === 0) return data;
    const sorted = [...data];
    sorted.sort((a, b) => {
      for (const sort of sortConfig) {
        const valA = (a as Record<string, unknown>)[sort.key];
        const valB = (b as Record<string, unknown>)[sort.key];

        if (valA == null && valB == null) continue;
        if (valA == null) return 1;
        if (valB == null) return -1;

        let comparison = 0;
        if (typeof valA === "string" && typeof valB === "string") {
          comparison = valA.localeCompare(valB);
        } else if (typeof valA === "number" && typeof valB === "number") {
          comparison = valA - valB;
        }

        if (comparison !== 0) {
          return sort.direction === "asc" ? comparison : -comparison;
        }
      }
      return 0;
    });
    return sorted;
  }, [data, sortConfig]);

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm text-left">
        <thead className="text-xs text-primary-500 uppercase bg-surface-50 dark:bg-primary-900/30">
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                className={`px-4 py-2 cursor-pointer hover:bg-surface-100 dark:hover:bg-primary-800 transition-colors select-none ${
                  col.headerClassName || ""
                }`}
                onClick={(e) => onSort(col.key, e)}
              >
                <span
                  className={
                    col.className ||
                    (col.key.includes("speed") || col.key.includes("accuracy") || col.key === "total_requests"
                      ? "flex items-center gap-1 justify-end"
                      : "flex items-center gap-1")
                  }
                >
                  {col.header}
                  <span className="text-primary-400">
                    {getSortDirectionIndicator(sortConfig, col.key)}
                  </span>
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sortedData.map((item, i) => {
            const key = rowKey(item, i);
            return (
            <tr
              key={key}
              onClick={() => onRowClick?.(item)}
              className={`border-b border-surface-100 dark:border-primary-800 ${
                rowClassName
                  ? rowClassName(item, i)
                  : ""
              } ${onRowClick ? "cursor-pointer" : ""}`}
            >
              {columns.map((col) => (
                <td
                  key={`${key}-${col.key}`}
                  className={`px-4 py-2 ${
                    col.cellClassName
                      ? col.cellClassName(item, i)
                      : "text-primary-600 dark:text-primary-400"
                  }`}
                >
                  {col.render
                    ? col.render(item)
                    : String((item as Record<string, unknown>)[col.key] ?? "")}
                </td>
              ))}
            </tr>
            );
          })}
        </tbody>
      </table>
      {hasActiveSort && onClearSort && (
        <div className="mt-2">
          <button
            onClick={onClearSort}
            className="rounded-md bg-surface-200 px-3 py-1.5 text-xs font-medium text-primary-700 hover:bg-surface-300 transition-colors"
          >
            Clear Sort
          </button>
        </div>
      )}
    </div>
  );
}