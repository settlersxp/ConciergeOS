import { useEffect, useState, useMemo } from "react";
import { performanceApi } from "../services/api";
import type { PerformanceStats } from "../types";
import { PageHeader, Card, StatusBanner, PerformanceChart } from "../components/ui";

interface SortConfig {
  key: keyof PerformanceStats;
  direction: "asc" | "desc";
}

export default function PerformanceDashboard() {
  const [data, setData] = useState<PerformanceStats[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [enabledBatches, setEnabledBatches] = useState<Set<string>>(new Set());
  // Batch search filter
  const [batchSearch, setBatchSearch] = useState("");
  // Multi-column sort: array of sort configs, first element is primary sort
  const [sortConfig, setSortConfig] = useState<SortConfig[]>([]);

  useEffect(() => {
    setLoading(true);
    setError(null);
    performanceApi
      .getPerformanceStats()
      .then((res) => {
        setData(res);
        // Enable all batches by default
        const allUuids = new Set<string>();
        for (const d of res) {
          allUuids.add(d.batch_uuid);
        }
        setEnabledBatches(allUuids);
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  const toggleBatch = (batchUuid: string) => {
    setEnabledBatches((prev) => {
      const next = new Set(prev);
      if (next.has(batchUuid)) {
        next.delete(batchUuid);
      } else {
        next.add(batchUuid);
      }
      return next;
    });
  };

  const selectAll = () => {
    const allUuids = new Set<string>();
    for (const d of data) {
      allUuids.add(d.batch_uuid);
    }
    setEnabledBatches(allUuids);
  };

  const deselectAll = () => {
    setEnabledBatches(new Set());
  };

  const filteredData = useMemo(
    () => data.filter((d) => enabledBatches.has(d.batch_uuid)),
    [data, enabledBatches]
  );

  const handleSort = (key: keyof PerformanceStats, event?: React.MouseEvent) => {
    setSortConfig((prev) => {
      // Check if Shift is held for multi-column sort
      if (event?.shiftKey) {
        // Check if this key already exists in the sort config
        const existingIndex = prev.findIndex((s) => s.key === key);
        if (existingIndex !== -1) {
          // Cycle direction for existing sort key
          const updated = prev.map((s, i) => {
            if (i === existingIndex) {
              if (s.direction === "asc") return { key, direction: "desc" as const };
              return { key, direction: "asc" as const };
            }
            return s;
          });
          // Move to end (highest priority)
          const moved = updated.splice(existingIndex, 1)[0];
          return [...updated, moved];
        }
        // Add new sort key
        return [...prev, { key, direction: "asc" as const }];
      }

      // No Shift: single-column sort (reset)
      const existing = prev.find((s) => s.key === key);
      if (existing) {
        // Cycle: asc -> desc -> clear
        if (existing.direction === "asc") {
          return [{ key, direction: "desc" as const }];
        }
        return [];
      }
      return [{ key, direction: "asc" as const }];
    });
  };

  const sortedData = useMemo(() => {
    if (sortConfig.length === 0) return filteredData;
    const sorted = [...filteredData];
    sorted.sort((a, b) => {
      for (const sort of sortConfig) {
        const valA = a[sort.key];
        const valB = b[sort.key];

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
        // If equal, continue to next sort key
      }
      return 0;
    });
    return sorted;
  }, [filteredData, sortConfig]);

  const getSortDirectionIndicator = (key: keyof PerformanceStats) => {
    const sort = sortConfig.find((s) => s.key === key);
    if (!sort) return null;
    const index = sortConfig.indexOf(sort);
    return `${index + 1}${sort.direction === "asc" ? " ↑" : " ↓"}`;
  };

  const clearSort = () => {
    setSortConfig([]);
  };

  const hasActiveSort = sortConfig.length > 0;

  const uniqueBatches = useMemo(() => {
    const map = new Map<string, PerformanceStats>();
    for (const d of data) {
      if (!map.has(d.batch_uuid)) {
        map.set(d.batch_uuid, d);
      }
    }
    return Array.from(map.values());
  }, [data]);

  const filteredBatches = useMemo(() => {
    if (!batchSearch.trim()) return uniqueBatches;
    const query = batchSearch.toLowerCase();
    return uniqueBatches.filter(
      (b) =>
        b.batch_uuid.toLowerCase().includes(query) ||
        b.friendly_name?.toLowerCase().includes(query)
    );
  }, [uniqueBatches, batchSearch]);

  if (loading) {
    return (
      <div className="mx-auto max-w-7xl p-6">
        <PageHeader title="Performance Dashboard" description="Visualize model performance across speed and accuracy dimensions" />
        <StatusBanner message="Loading performance data..." type="running" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-7xl p-6">
        <PageHeader title="Performance Dashboard" description="Visualize model performance across speed and accuracy dimensions" />
        <StatusBanner message={error} type="error" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl p-6 space-y-6">
      <div className="flex items-center justify-between">
        <PageHeader
          title="Performance Dashboard"
          description="Visualize model performance across speed and accuracy dimensions"
        />
        <div className="flex gap-2">
          <button
            onClick={selectAll}
            className="rounded-md bg-primary-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-primary-700 transition-colors"
          >
            Select All
          </button>
          <button
            onClick={deselectAll}
            className="rounded-md bg-surface-200 px-3 py-1.5 text-xs font-medium text-primary-700 hover:bg-surface-300 transition-colors"
          >
            Deselect All
          </button>
          {hasActiveSort && (
            <button
              onClick={clearSort}
              className="rounded-md bg-surface-200 px-3 py-1.5 text-xs font-medium text-primary-700 hover:bg-surface-300 transition-colors"
            >
              Clear Sort
            </button>
          )}
        </div>
      </div>

      {data.length === 0 ? (
        <Card title="No Data" description="Run some performance tests to see results here">
          <div className="text-center py-12 text-primary-400 text-sm">
            No performance test data available yet.
          </div>
        </Card>
      ) : (
        <>
          {/* Chart */}
          <Card title="Performance Scatter Plot" description="X-axis: Response time (lower is better) · Y-axis: Accuracy (higher is better)">
            <PerformanceChart
              data={data}
              visibleBatches={enabledBatches}
              onToggleBatch={(batchUuid) => toggleBatch(batchUuid)}
            />
          </Card>

          {/* Batch toggles */}
          <Card
            title="Batch Controls"
            description="Enable or disable batches from the visualization"
          >
            <div className="mb-3">
              <input
                type="text"
                placeholder="Search batches by name or ID..."
                value={batchSearch}
                onChange={(e) => setBatchSearch(e.target.value)}
                className="w-full rounded-md border border-surface-200 bg-surface-50 px-3 py-2 text-sm text-primary-700 placeholder-primary-400 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-primary-800 dark:bg-primary-900/30 dark:text-primary-300 dark:placeholder-primary-600"
              />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 mt-2">
              {filteredBatches.map((b) => (
                <label
                  key={b.batch_uuid}
                  className={`flex items-center gap-2 rounded-md px-3 py-2 cursor-pointer transition-colors ${
                    enabledBatches.has(b.batch_uuid)
                      ? "bg-primary-50 border border-primary-200 dark:bg-primary-900/30 dark:border-primary-700"
                      : "bg-surface-50 border border-surface-200 opacity-50 dark:bg-primary-900/20 dark:border-primary-800"
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={enabledBatches.has(b.batch_uuid)}
                    onChange={() => toggleBatch(b.batch_uuid)}
                    className="h-4 w-4 rounded border-surface-300 text-primary-600 focus:ring-primary-500"
                  />
                  <span className="text-sm text-primary-700 dark:text-primary-300 truncate">
                    {b.friendly_name || b.batch_uuid.slice(0, 8)}
                  </span>
                </label>
              ))}
            </div>
          </Card>

          {/* Stats table */}
          <Card
            title="Detailed Statistics"
            description="Per-batch aggregated performance metrics"
          >
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="text-xs text-primary-500 uppercase bg-surface-50 dark:bg-primary-900/30">
                  <tr>
                    <th
                      className="px-4 py-2 cursor-pointer hover:bg-surface-100 dark:hover:bg-primary-800 transition-colors select-none tooltip-parent group relative"
                      onClick={(e) => handleSort("friendly_name", e)}
                      title="Click to sort. Hold Shift and click other columns to add multi-sort."
                    >
                      <span className="flex items-center gap-1">
                        Friendly Name
                        <span className="text-primary-400">
                          {getSortDirectionIndicator("friendly_name")}
                        </span>
                      </span>
                    </th>
                    <th
                      className="px-4 py-2 cursor-pointer hover:bg-surface-100 dark:hover:bg-primary-800 transition-colors select-none"
                      onClick={(e) => handleSort("model_name", e)}
                      title="Click to sort. Hold Shift and click other columns to add multi-sort."
                    >
                      <span className="flex items-center gap-1">
                        Model
                        <span className="text-primary-400">
                          {getSortDirectionIndicator("model_name")}
                        </span>
                      </span>
                    </th>
                    <th
                      className="px-4 py-2 cursor-pointer hover:bg-surface-100 dark:hover:bg-primary-800 transition-colors select-none"
                      onClick={(e) => handleSort("batch_type", e)}
                      title="Click to sort. Hold Shift and click other columns to add multi-sort."
                    >
                      <span className="flex items-center gap-1">
                        Batch Type
                        <span className="text-primary-400">
                          {getSortDirectionIndicator("batch_type")}
                        </span>
                      </span>
                    </th>
                    <th
                      className="px-4 py-2 cursor-pointer hover:bg-surface-100 dark:hover:bg-primary-800 transition-colors select-none text-right"
                      onClick={(e) => handleSort("avg_speed_seconds", e)}
                      title="Click to sort. Hold Shift and click other columns to add multi-sort."
                    >
                      <span className="flex items-center gap-1 justify-end">
                        Avg Speed (s)
                        <span className="text-primary-400">
                          {getSortDirectionIndicator("avg_speed_seconds")}
                        </span>
                      </span>
                    </th>
                    <th
                      className="px-4 py-2 cursor-pointer hover:bg-surface-100 dark:hover:bg-primary-800 transition-colors select-none text-right"
                      onClick={(e) => handleSort("accuracy_pct", e)}
                      title="Click to sort. Hold Shift and click other columns to add multi-sort."
                    >
                      <span className="flex items-center gap-1 justify-end">
                        Accuracy (%)
                        <span className="text-primary-400">
                          {getSortDirectionIndicator("accuracy_pct")}
                        </span>
                      </span>
                    </th>
                    <th
                      className="px-4 py-2 cursor-pointer hover:bg-surface-100 dark:hover:bg-primary-800 transition-colors select-none text-right"
                      onClick={(e) => handleSort("total_requests", e)}
                      title="Click to sort. Hold Shift and click other columns to add multi-sort."
                    >
                      <span className="flex items-center gap-1 justify-end">
                        Requests
                        <span className="text-primary-400">
                          {getSortDirectionIndicator("total_requests")}
                        </span>
                      </span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {sortedData.map((d, i) => (
                    <tr
                      key={`${d.batch_uuid}-${d.batch_type}-${i}`}
                      className={`border-b border-surface-100 dark:border-primary-800 ${
                        enabledBatches.has(d.batch_uuid)
                          ? ""
                          : "opacity-40"
                      }`}
                    >
                      <td className="px-4 py-2 font-medium text-primary-700 dark:text-primary-300">
                        {d.friendly_name || "—"}
                      </td>
                      <td className="px-4 py-2 text-primary-600 dark:text-primary-400">
                        {d.model_name}
                      </td>
                      <td className="px-4 py-2">
                        <span
                          className={`text-xs px-1.5 py-0.5 rounded ${
                            d.batch_type === "sequential"
                              ? "bg-primary-100 text-primary-600 dark:bg-primary-900/30 dark:text-primary-400"
                              : "bg-secondary-100 text-secondary-600 dark:bg-secondary-900/30 dark:text-secondary-400"
                          }`}
                        >
                          {d.batch_type}
                        </span>
                      </td>
                      <td className="px-4 py-2 font-mono text-primary-600 dark:text-primary-400 text-right">
                        {d.avg_speed_seconds.toFixed(3)}
                      </td>
                      <td className="px-4 py-2 font-mono text-primary-600 dark:text-primary-400 text-right">
                        {d.accuracy_pct}
                      </td>
                      <td className="px-4 py-2 text-primary-600 dark:text-primary-400 text-right">
                        {d.total_requests}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}