import React from "react";

export interface GroupedColumn<TRow> {
  key: string;
  header: string;
  className?: string;
  headerClassName?: string;
  render?: (row: TRow) => React.ReactNode;
  cellClassName?: (row: TRow) => string;
}

interface GroupedRow<_TGroup, TRow> {
  groupKey: string;
  groupLabel: string;
  subRows: TRow[];
}

interface GroupedDataTableProps<TGroup, TRow> {
  groups: GroupedRow<TGroup, TRow>[];
  columns: GroupedColumn<TRow>[];
  rowKey?: (row: TRow, globalIndex: number) => string;
  subRowLabel?: (row: TRow) => React.ReactNode;
  rowClassName?: (row: TRow, groupIndex: number) => string;
}

export default function GroupedDataTable<TGroup, TRow>({
  groups,
  columns,
  rowKey,
  subRowLabel,
  rowClassName,
}: GroupedDataTableProps<TGroup, TRow>) {
  const getKey = rowKey || ((_row: TRow, globalIndex: number) => String(globalIndex));

  // Flatten groups into a single array with group index metadata
  const flattenedRows = React.useMemo(() => {
    const result: { row: TRow; groupIndex: number; isFirstChild: boolean }[] = [];
    groups.forEach((group, groupIndex) => {
      group.subRows.forEach((subRow) => {
        result.push({ row: subRow, groupIndex, isFirstChild: true });
      });
    });
    return result;
  }, [groups]);

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm text-left">
        <thead className="text-xs text-primary-500 uppercase bg-surface-50 dark:bg-primary-900/30">
          <tr>
            <th className="px-4 py-2">#</th>
            <th className="px-4 py-2">Batch</th>
            {columns.map((col) => (
              <th
                key={col.key}
                className={`px-4 py-2 ${col.headerClassName || ""}`}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-surface-100 dark:divide-primary-800">
          {flattenedRows.map(({ row, groupIndex, isFirstChild }, globalIndex) => {
            const key = getKey(row, globalIndex);
            const evenGroup = groupIndex % 2 === 0;
            const rowBg = evenGroup
              ? "bg-surface-50 dark:bg-primary-900/20"
              : "bg-surface-100/50 dark:bg-primary-800/20";
            const displayRowClass = rowClassName
              ? rowClassName(row, groupIndex)
              : rowBg;

            return (
              <tr key={key} className={displayRowClass}>
                <td className="px-4 py-2 text-primary-500 dark:text-primary-400 text-xs">
                  {isFirstChild ? String(globalIndex + 1) : ""}
                </td>
                <td className="px-4 py-2 font-medium text-primary-700 dark:text-primary-300">
                  {isFirstChild ? (
                    <span className="text-xs font-mono">{groups[groupIndex].groupLabel}</span>
                  ) : subRowLabel ? (
                    subRowLabel(row)
                  ) : (
                    ""
                  )}
                </td>
                {columns.map((col) => (
                  <td
                    key={`${key}-${col.key}`}
                    className={`px-4 py-2 ${
                      col.cellClassName
                        ? col.cellClassName(row)
                        : "text-primary-600 dark:text-primary-400"
                    }`}
                  >
                    {col.render ? col.render(row) : ""}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}