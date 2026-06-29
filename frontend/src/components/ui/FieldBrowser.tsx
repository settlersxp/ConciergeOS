import { useState } from "react";
import { Badge } from "./";

type FieldInfo = {
  field: string;
  type: string;
  constraints: string[];
  nullable: boolean;
  primary_key: boolean;
  foreign_keys: string[];
};

type FieldSchema = Record<string, FieldInfo[]>;

interface FieldBrowserProps {
  schema: FieldSchema;
  onInsert: (key: string) => void;
  onClose: () => void;
}

/** Filterable field browser showing all available database tables/columns. */
export default function FieldBrowser({ schema, onInsert, onClose }: FieldBrowserProps) {
  const [search, setSearch] = useState("");

  const matchesFilter = (tableName: string, fieldInfo: FieldInfo): boolean => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (
      tableName.toLowerCase().includes(q) ||
      fieldInfo.field.toLowerCase().includes(q) ||
      fieldInfo.type.toLowerCase().includes(q) ||
      fieldInfo.constraints.some((c) => c.toLowerCase().includes(q))
    );
  };

  const tables = Object.entries(schema)
    .map(([table, fields]) => ({ table, fields }))
    .filter(({ table, fields }) => fields.some((f) => matchesFilter(table, f)))
    .sort((a, b) => a.table.localeCompare(b.table));

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-surface-50 dark:bg-primary-800 rounded-xl shadow-2xl w-full max-w-2xl max-h-[80vh] flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header — matches ValidationModal header styling */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-surface-200 dark:border-primary-700">
          <h3 className="text-lg font-bold text-primary-900 dark:text-white">
            Browse Available Fields
          </h3>
          <button
            onClick={onClose}
            className="text-primary-400 hover:text-primary-600 dark:hover:text-primary-200 text-2xl leading-none"
          >
            &times;
          </button>
        </div>

        {/* Search */}
        <div className="px-6 py-3 border-b border-surface-200 dark:border-primary-700">
          <input
            type="text"
            placeholder="Search tables, fields, types..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full px-3 py-2 text-sm bg-white dark:bg-primary-700 border border-surface-200 dark:border-primary-600 rounded-md text-primary-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-5">
          {tables.length === 0 ? (
            <p className="text-sm text-primary-500 dark:text-primary-400 text-center py-8">
              No fields match your search.
            </p>
          ) : (
            tables.map(({ table, fields }) => (
              <div key={table}>
                <div className="flex items-center gap-2 mb-2">
                  <h4 className="text-sm font-semibold text-primary-800 dark:text-primary-200">
                    {table}
                  </h4>
                  <Badge variant="neutral">{fields.length}</Badge>
                </div>
                <div className="overflow-x-auto rounded-lg border border-surface-200 dark:border-primary-700">
                  <table className="w-full text-xs">
                    <thead className="bg-surface-100 dark:bg-primary-700">
                      <tr>
                        <th className="px-3 py-2 text-left font-medium text-primary-500 dark:text-primary-300">Field</th>
                        <th className="px-3 py-2 text-left font-medium text-primary-500 dark:text-primary-300">Type</th>
                        <th className="px-3 py-2 text-left font-medium text-primary-500 dark:text-primary-300">Constraints</th>
                        <th className="px-3 py-2 text-center font-medium text-primary-500 dark:text-primary-300">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-surface-200 dark:divide-primary-700">
                      {fields
                        .filter((f) => matchesFilter(table, f))
                        .map((f) => (
                          <tr key={f.field} className="bg-white dark:bg-primary-800 hover:bg-surface-50 dark:hover:bg-primary-700/50">
                            <td className="px-3 py-2 font-mono text-primary-900 dark:text-white">
                              {f.field}
                            </td>
                            <td className="px-3 py-2 text-primary-600 dark:text-primary-300">
                              {f.type}
                            </td>
                            <td className="px-3 py-2">
                              <div className="flex flex-wrap gap-1">
                                {f.primary_key && <Badge variant="warning">PK</Badge>}
                                {!f.nullable && <Badge variant="neutral">NOT NULL</Badge>}
                                {f.foreign_keys.map((fk) => (
                                  <Badge key={fk} variant="neutral">
                                    FK→{fk.split(".")[1] || fk}
                                  </Badge>
                                ))}
                              </div>
                            </td>
                            <td className="px-3 py-2 text-center">
                              <button
                                onClick={() => onInsert(`${table}.${f.field}`)}
                                className="text-[#87d372] hover:text-[#6fbf5a] text-xs font-medium"
                              >
                                + Insert
                              </button>
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Footer — matches ValidationModal footer styling */}
        <div className="px-6 py-3 border-t border-surface-200 dark:border-primary-700 text-xs text-primary-500 dark:text-primary-400">
          Click <span className="font-medium">+ Insert</span> to add a field to your runtime variables.
        </div>
      </div>
    </div>
  );
}