import { useEffect, useState, useMemo, useCallback, useRef } from "react";
import { performanceApi } from "../services/api";
import type { PerformanceStats, PromptBatchStatsResponse, GroupedBatch, BatchTypeRow } from "../types";
import { PageHeader, Card, StatusBanner, PerformanceChart, PromptSelector } from "../components/ui";

interface SortConfig {
  key: keyof PerformanceStats;
  direction: "asc" | "desc";
}

type ViewMode = "batch" | "prompt";

export default function PerformanceDashboard() {
  // Batch view state
  const [batchData, setBatchData] = useState<PerformanceStats[]>([]);
  const [batchLoading, setBatchLoading] = useState(true);
  const [batchError, setBatchError] = useState<string | null>(null);
  const [enabledBatches, setEnabledBatches] = useState<Set<string>>(new Set());
  const [batchSearch, setBatchSearch] = useState("");
  const [batchSortConfig, setBatchSortConfig] = useState<SortConfig[]>([]);

  // Prompt view state
  const [viewMode, setViewMode] = useState<ViewMode>("batch");
  const [selectedSelection, setSelectedSelection] = useState<{ prompt_id: string; version?: number } | null>(null);
  const [promptBatchStats, setPromptBatchStats] = useState<PromptBatchStatsResponse | null>(null);
  const [promptStatsLoading, setPromptStatsLoading] = useState(false);
  const [promptError, setPromptError] = useState<string | null>(null);

  // Load batch data
  useEffect(() => {
    if (viewMode !== "batch") return;
    setBatchLoading(true);
    setBatchError(null);
    performanceApi
      .getPerformanceStats()
      .then((res) => {
        setBatchData(res);
        const allUuids = new Set<string>();
        for (const d of res) {
          allUuids.add(d.batch_uuid);
        }
        setEnabledBatches(allUuids);
      })
      .catch((e) => {
        setBatchError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        setBatchLoading(false);
      });
  }, [viewMode]);

  // Load prompt batch stats when selection changes
  // Track the last fetched selection to prevent redundant API calls
  // Use a ref so it persists across renders without triggering re-renders
  const lastFetchedRef = useRef<{ prompt_id: string; version?: number } | null>(null);

  useEffect(() => {
    if (!selectedSelection || viewMode !== "prompt") {
      setPromptBatchStats(null);
      lastFetchedRef.current = null;
      return;
    }

    // Skip if this exact selection was already fetched
    const last = lastFetchedRef.current;
    if (last && last.prompt_id === selectedSelection.prompt_id && last.version === selectedSelection.version) {
      return;
    }

    setPromptStatsLoading(true);
    setPromptError(null);
    lastFetchedRef.current = { prompt_id: selectedSelection.prompt_id, version: selectedSelection.version };

    performanceApi
      .getPromptBatchStats(selectedSelection.prompt_id, selectedSelection.version)
      .then((res) => {
        // Only update if the selection hasn't changed since we started fetching
        const current = lastFetchedRef.current;
        if (current && current.prompt_id === selectedSelection.prompt_id && current.version === selectedSelection.version) {
          setPromptBatchStats(res);
        }
      })
      .catch((e) => {
        const current = lastFetchedRef.current;
        if (current && current.prompt_id === selectedSelection.prompt_id && current.version === selectedSelection.version) {
          setPromptError(e instanceof Error ? e.message : String(e));
        }
      })
      .finally(() => {
        const current = lastFetchedRef.current;
        if (current && current.prompt_id === selectedSelection.prompt_id && current.version === selectedSelection.version) {
          setPromptStatsLoading(false);
        }
      });
  }, [selectedSelection, viewMode]);

  const handlePromptSelectionChange = useCallback((value: { prompt_id: string; version?: number }) => {
    setSelectedSelection(value);
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
    for (const d of batchData) {
      allUuids.add(d.batch_uuid);
    }
    setEnabledBatches(allUuids);
  };

  const deselectAll = () => {
    setEnabledBatches(new Set());
  };

  const filteredBatchData = useMemo(
    () => batchData.filter((d) => enabledBatches.has(d.batch_uuid)),
    [batchData, enabledBatches]
  );

  const handleBatchSort = (key: keyof PerformanceStats, event?: React.MouseEvent) => {
    setBatchSortConfig((prev) => {
      if (event?.shiftKey) {
        const existingIndex = prev.findIndex((s) => s.key === key);
        if (existingIndex !== -1) {
          const updated = prev.map((s, i) => {
            if (i === existingIndex) {
              if (s.direction === "asc") return { key, direction: "desc" as const };
              return { key, direction: "asc" as const };
            }
            return s;
          });
          const moved = updated.splice(existingIndex, 1)[0];
          return [...updated, moved];
        }
        return [...prev, { key, direction: "asc" as const }];
      }

      const existing = prev.find((s) => s.key === key);
      if (existing) {
        if (existing.direction === "asc") {
          return [{ key, direction: "desc" as const }];
        }
        return [];
      }
      return [{ key, direction: "asc" as const }];
    });
  };

  const sortedBatchData = useMemo(() => {
    if (batchSortConfig.length === 0) return filteredBatchData;
    const sorted = [...filteredBatchData];
    sorted.sort((a, b) => {
      for (const sort of batchSortConfig) {
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
      }
      return 0;
    });
    return sorted;
  }, [filteredBatchData, batchSortConfig]);

  const getSortDirectionIndicator = (key: keyof PerformanceStats) => {
    const sort = batchSortConfig.find((s) => s.key === key);
    if (!sort) return null;
    const index = batchSortConfig.indexOf(sort);
    return `${index + 1}${sort.direction === "asc" ? " ↑" : " ↓"}`;
  };

  const clearSort = () => {
    setBatchSortConfig([]);
  };

  const hasActiveSort = batchSortConfig.length > 0;

  const uniqueBatches = useMemo(() => {
    const map = new Map<string, PerformanceStats>();
    for (const d of batchData) {
      if (!map.has(d.batch_uuid)) {
        map.set(d.batch_uuid, d);
      }
    }
    return Array.from(map.values());
  }, [batchData]);

  const filteredBatches = useMemo(() => {
    if (!batchSearch.trim()) return uniqueBatches;
    const query = batchSearch.toLowerCase();
    return uniqueBatches.filter(
      (b) =>
        b.batch_uuid.toLowerCase().includes(query) ||
        b.friendly_name?.toLowerCase().includes(query)
    );
  }, [uniqueBatches, batchSearch]);

  // Batch chart data - each batch is a dot, individual timings shown as error range
  const batchChartData = useMemo(() => {
    if (!promptBatchStats?.batches) return [];
    return promptBatchStats.batches.map((batch) => ({
      batch_uuid: batch.batch_uuid,
      friendly_name: batch.friendly_name || batch.batch_uuid.slice(0, 8),
      model_name: batch.model_name,
      batch_type: batch.batch_type as "sequential" | "concurrent",
      avg_speed_seconds: batch.avg_speed_seconds,
      accuracy_pct: batch.accuracy_pct,
      total_requests: batch.total_requests,
      // Additional metadata for tooltips
      min_speed_seconds: batch.min_speed_seconds,
      max_speed_seconds: batch.max_speed_seconds,
      individual_timings: batch.individual_timings,
    }));
  }, [promptBatchStats]);

  // Group batches by friendly_name for the reorganized Batch Details table
  // Each group contains concurrent and/or sequential sub-rows
  // An overall accuracy is computed as the average of concurrent and sequential accuracies
  const groupedBatches = useMemo<GroupedBatch[]>(() => {
    if (!promptBatchStats?.batches) return [];
    const nameMap = new Map<string, GroupedBatch>();
    const insertionOrder: string[] = [];

    for (const batch of promptBatchStats.batches) {
      const name = batch.friendly_name || batch.batch_uuid;
      let gb = nameMap.get(name);
      if (!gb) {
        gb = { batch_name: name, batch_uuids: [], model_name: batch.model_name, types: {} };
        nameMap.set(name, gb);
        insertionOrder.push(name);
      }
      const row: BatchTypeRow = {
        avg_speed_seconds: batch.avg_speed_seconds,
        min_speed_seconds: batch.min_speed_seconds,
        max_speed_seconds: batch.max_speed_seconds,
        accuracy_pct: batch.accuracy_pct,
        total_requests: batch.total_requests,
      };
      const btype = batch.batch_type as "concurrent" | "sequential";
      (gb.types as any)[btype] = row;
      if (!gb.batch_uuids.includes(batch.batch_uuid)) {
        gb.batch_uuids.push(batch.batch_uuid);
      }
    }

    // Compute overall accuracy per batch (average of concurrent and sequential)
    for (const gb of nameMap.values()) {
      if (gb.types.concurrent && gb.types.sequential) {
        gb.types.overall_avg_speed =
          (gb.types.concurrent.avg_speed_seconds + gb.types.sequential.avg_speed_seconds) / 2;
        gb.types.overall_accuracy =
          (gb.types.concurrent.accuracy_pct + gb.types.sequential.accuracy_pct) / 2;
        gb.types.overall_total_requests =
          (gb.types.concurrent.total_requests + gb.types.sequential.total_requests);
        gb.types.overall_min_speed = Math.min(
          gb.types.concurrent.min_speed_seconds,
          gb.types.sequential.min_speed_seconds
        );
        gb.types.overall_max_speed = Math.max(
          gb.types.concurrent.max_speed_seconds,
          gb.types.sequential.max_speed_seconds
        );
      } else if (gb.types.concurrent) {
        gb.types.overall_avg_speed = gb.types.concurrent.avg_speed_seconds;
        gb.types.overall_accuracy = gb.types.concurrent.accuracy_pct;
        gb.types.overall_total_requests = gb.types.concurrent.total_requests;
        gb.types.overall_min_speed = gb.types.concurrent.min_speed_seconds;
        gb.types.overall_max_speed = gb.types.concurrent.max_speed_seconds;
      } else if (gb.types.sequential) {
        gb.types.overall_avg_speed = gb.types.sequential.avg_speed_seconds;
        gb.types.overall_accuracy = gb.types.sequential.accuracy_pct;
        gb.types.overall_total_requests = gb.types.sequential.total_requests;
        gb.types.overall_min_speed = gb.types.sequential.min_speed_seconds;
        gb.types.overall_max_speed = gb.types.sequential.max_speed_seconds;
      }
    }

    // Sort by overall accuracy descending
    return insertionOrder
      .map((n) => nameMap.get(n)!)
      .filter(Boolean)
      .sort((a, b) => {
        const accA = a.types.overall_accuracy ?? 0;
        const accB = b.types.overall_accuracy ?? 0;
        return accB - accA;
      });
  }, [promptBatchStats]);

  // ── Render: Loading ──

  if (viewMode === "batch" && batchLoading) {
    return (
      <div className="mx-auto max-w-7xl p-6">
        <PageHeader title="Performance Dashboard" description="Visualize model performance across speed and accuracy dimensions" />
        <StatusBanner message="Loading performance data..." type="running" />
      </div>
    );
  }

  // ── Render: Error ──

  if (viewMode === "batch" && batchError) {
    return (
      <div className="mx-auto max-w-7xl p-6">
        <PageHeader title="Performance Dashboard" description="Visualize model performance across speed and accuracy dimensions" />
        <StatusBanner message={batchError} type="error" />
      </div>
    );
  }

  // ── Render: Main Content ──

  return (
    <div className="mx-auto max-w-7xl p-6 space-y-6">
      {/* Header with view mode toggle */}
      <div className="flex items-center justify-between">
        <PageHeader
          title="Performance Dashboard"
          description={viewMode === "batch"
            ? "Visualize model performance across speed and accuracy dimensions"
            : "Analyze performance by prompt"}
        />
        <div className="flex gap-3 items-center">
          {/* View mode toggle */}
          <div className="flex rounded-lg border border-surface-200 dark:border-primary-800 overflow-hidden">
            <button
              onClick={() => setViewMode("batch")}
              className={`px-4 py-1.5 text-sm font-medium transition-colors ${
                viewMode === "batch"
                  ? "bg-primary-600 text-white"
                  : "bg-surface-50 text-primary-600 hover:bg-surface-100 dark:bg-primary-900/30 dark:text-primary-400 dark:hover:bg-primary-900/50"
              }`}
            >
              Batch View
            </button>
            <button
              onClick={() => setViewMode("prompt")}
              className={`px-4 py-1.5 text-sm font-medium transition-colors ${
                viewMode === "prompt"
                  ? "bg-primary-600 text-white"
                  : "bg-surface-50 text-primary-600 hover:bg-surface-100 dark:bg-primary-900/30 dark:text-primary-400 dark:hover:bg-primary-900/50"
              }`}
            >
              Prompt View
            </button>
          </div>

          {viewMode === "batch" && (
            <>
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
            </>
          )}
        </div>
      </div>

      {/* ── Batch View ── */}
      {viewMode === "batch" && (
        <>
          {batchData.length === 0 ? (
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
                  data={batchData}
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
                          className="px-4 py-2 cursor-pointer hover:bg-surface-100 dark:hover:bg-primary-800 transition-colors select-none"
                          onClick={(e) => handleBatchSort("friendly_name", e)}
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
                          onClick={(e) => handleBatchSort("model_name", e)}
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
                          onClick={(e) => handleBatchSort("batch_type", e)}
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
                          onClick={(e) => handleBatchSort("avg_speed_seconds", e)}
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
                          onClick={(e) => handleBatchSort("accuracy_pct", e)}
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
                          onClick={(e) => handleBatchSort("total_requests", e)}
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
                      {sortedBatchData.map((d, i) => (
                        <tr
                          key={`${d.batch_uuid}-${d.batch_type}-${i}`}
                          className={`border-b border-surface-100 dark:border-primary-800 ${
                            enabledBatches.has(d.batch_uuid) ? "" : "opacity-40"
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
        </>
      )}

      {/* ── Prompt View ── */}
      {viewMode === "prompt" && (
        <>
          {/* Prompt selector */}
          <Card
            title="Prompt Selector"
            description="Select a prompt to view detailed performance analysis"
          >
            <PromptSelector
              onChange={handlePromptSelectionChange}
            />
          </Card>

          {/* Prompt detail error */}
          {promptError && selectedSelection && (
            <StatusBanner message={promptError} type="error" />
          )}

          {/* Inline loading indicator (doesn't flash the whole page) */}
          {selectedSelection && promptStatsLoading && !promptBatchStats && (
            <div className="flex items-center justify-center py-12">
              <div className="text-center">
                <div className="inline-block h-6 w-6 animate-spin rounded-full border-4 border-solid border-current border-r-transparent align-[-0.125em] motion-reduce:animate-[spin_1.5s_linear_infinite]"></div>
                <p className="mt-2 text-sm text-primary-500 dark:text-primary-400">Loading performance data...</p>
              </div>
            </div>
          )}

          {/* Selected prompt batch stats */}
          {selectedSelection && promptBatchStats && (
            <>
              {/* Summary cards */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <Card title="Avg Speed" description="Seconds per request">
                  <div className="text-2xl font-mono font-bold text-primary-700 dark:text-primary-300">
                    {promptBatchStats.overall_avg_speed.toFixed(3)}s
                  </div>
                </Card>
                <Card title="Accuracy" description="Valid response rate">
                  <div className="text-2xl font-mono font-bold text-primary-700 dark:text-primary-300">
                    {promptBatchStats.overall_accuracy}%
                  </div>
                </Card>
                <Card title="Total Batches" description="Number of test batches">
                  <div className="text-2xl font-mono font-bold text-primary-700 dark:text-primary-300">
                    {promptBatchStats.total_batches}
                  </div>
                </Card>
                <Card title="Total Requests" description="Individual requests">
                  <div className="text-2xl font-mono font-bold text-primary-700 dark:text-primary-300">
                    {promptBatchStats.total_requests}
                  </div>
                </Card>
              </div>

              {/* Batch performance chart */}
              <Card title="Batch Performance" description={`Batches for ${promptBatchStats.prompt_name} v${promptBatchStats.prompt_version ?? 'default'} · X-axis: Avg Speed (lower is better) · Y-axis: Accuracy (higher is better)`}>
                <PerformanceChart
                  data={batchChartData}
                />
              </Card>

              {/* Batch details table - grouped by batch name with type sub-rows */}
              <Card
                title="Batch Details"
                description={`Grouped results for ${promptBatchStats.prompt_name}`}
              >
                <div className="overflow-x-auto">
                  <table className="w-full text-sm text-left">
                    <thead className="text-xs text-primary-500 uppercase bg-surface-50 dark:bg-primary-900/30">
                      <tr>
                        <th className="px-4 py-2">#</th>
                        <th className="px-4 py-2">Batch</th>
                        <th className="px-4 py-2">Type</th>
                        <th className="px-4 py-2 text-right">Avg (s)</th>
                        <th className="px-4 py-2 text-right">Min (s)</th>
                        <th className="px-4 py-2 text-right">Max (s)</th>
                        <th className="px-4 py-2 text-center">Accuracy</th>
                        <th className="px-4 py-2 text-right">Requests</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-surface-100 dark:divide-primary-800">
                      {(() => {
                        const rows: React.ReactNode[] = [];
                        let batchIdx = 0;
                        for (const gb of groupedBatches) {
                          const batchColor = batchIdx % 2 === 0 ? "" : "bg-surface-100/50 dark:bg-primary-800/20";
                          const hasConcurrent = !!gb.types.concurrent;
                          const hasSequential = !!gb.types.sequential;

                          if (hasConcurrent) {
                            rows.push(
                              <tr key={`${gb.batch_name}-concurrent`} className={batchColor}>
                                <td className="px-4 py-2 text-primary-500 dark:text-primary-400 text-xs">
                                  {batchIdx + 1}
                                </td>
                                <td className="px-4 py-2 font-medium text-primary-700 dark:text-primary-300">
                                  <span className="text-xs font-mono">{gb.batch_name}</span>
                                </td>
                                <td className="px-4 py-2">
                                  <span
                                    className="text-xs px-1.5 py-0.5 rounded bg-secondary-100 text-secondary-600 dark:bg-secondary-900/30 dark:text-secondary-400"
                                  >
                                    concurrent
                                  </span>
                                </td>
                                <td className="px-4 py-2 font-mono text-primary-600 dark:text-primary-400 text-right">
                                  {gb.types.concurrent!.avg_speed_seconds.toFixed(3)}
                                </td>
                                <td className="px-4 py-2 font-mono text-green-600 dark:text-green-400 text-right">
                                  {gb.types.concurrent!.min_speed_seconds.toFixed(3)}
                                </td>
                                <td className="px-4 py-2 font-mono text-red-600 dark:text-red-400 text-right">
                                  {gb.types.concurrent!.max_speed_seconds.toFixed(3)}
                                </td>
                                <td className="px-4 py-2 text-center font-mono text-primary-600 dark:text-primary-400">
                                  {gb.types.concurrent!.accuracy_pct}%
                                </td>
                                <td className="px-4 py-2 text-primary-600 dark:text-primary-400 text-right">
                                  {gb.types.concurrent!.total_requests}
                                </td>
                              </tr>
                            );
                          }

                          if (hasSequential) {
                            rows.push(
                              <tr key={`${gb.batch_name}-sequential`} className={batchColor}>
                                <td className="px-4 py-2 text-primary-500 dark:text-primary-400 text-xs"></td>
                                <td className="px-4 py-2 font-medium text-primary-700 dark:text-primary-300"></td>
                                <td className="px-4 py-2">
                                  <span
                                    className="text-xs px-1.5 py-0.5 rounded bg-primary-100 text-primary-600 dark:bg-primary-900/30 dark:text-primary-400"
                                  >
                                    sequential
                                  </span>
                                </td>
                                <td className="px-4 py-2 font-mono text-primary-600 dark:text-primary-400 text-right">
                                  {gb.types.sequential!.avg_speed_seconds.toFixed(3)}
                                </td>
                                <td className="px-4 py-2 font-mono text-green-600 dark:text-green-400 text-right">
                                  {gb.types.sequential!.min_speed_seconds.toFixed(3)}
                                </td>
                                <td className="px-4 py-2 font-mono text-red-600 dark:text-red-400 text-right">
                                  {gb.types.sequential!.max_speed_seconds.toFixed(3)}
                                </td>
                                <td className="px-4 py-2 text-center font-mono text-primary-600 dark:text-primary-400">
                                  {gb.types.sequential!.accuracy_pct}%
                                </td>
                                <td className="px-4 py-2 text-primary-600 dark:text-primary-400 text-right">
                                  {gb.types.sequential!.total_requests}
                                </td>
                              </tr>
                            );
                          }
                          batchIdx++;
                        }
                        return rows;
                      })()}
                    </tbody>
                  </table>
                </div>
              </Card>
            </>
          )}

          {/* No batch data yet */}
          {selectedSelection && !promptBatchStats && !promptStatsLoading && !promptError && (
            <Card title="No Data" description="Select a prompt and version to view performance analysis">
              <div className="text-center py-12 text-primary-400 text-sm">
                No performance data available for this prompt. Run tests with prompt_id and prompt_version set.
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );
}