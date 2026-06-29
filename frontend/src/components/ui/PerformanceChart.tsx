import { useMemo, useState } from "react";
import type { PerformanceStats } from "../../types";
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
} from "recharts";
import Badge from "./Badge";

// Hash function: string → integer
function hashString(str: string): number {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash; // Convert to 32bit integer
  }
  return Math.abs(hash);
}

// Rainbow color generator: assigns HSL colors evenly across the spectrum
// based on the batch's index among all unique batches
function getBatchColor(batchUuid: string, totalBatches: number): string {
  if (totalBatches <= 1) return "hsl(260, 70%, 55%)"; // purple for single batch
  const hue = (hashString(batchUuid) % totalBatches) * (360 / totalBatches);
  return `hsl(${hue}, 70%, 55%)`;
}

interface PerformanceChartProps {
  data: PerformanceStats[];
}

interface TooltipEntry {
  batch_uuid: string;
  friendly_name: string;
  model_name: string;
  batch_type: string;
  avg_speed_seconds: number;
  accuracy_pct: number;
  total_requests: number;
}

function CustomTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{
    payload: TooltipEntry;
  }>;
}) {
  if (!active || !payload || !payload.length) return null;
  const d = payload[0].payload;
  return (
    <div className="rounded-lg border border-surface-200 bg-white p-3 shadow-lg dark:bg-primary-800">
      <p className="font-semibold text-primary-900 dark:text-white">
        {d.friendly_name}
      </p>
      <p className="text-xs text-primary-500 dark:text-primary-300">
        {d.model_name}
      </p>
      <div className="mt-2 space-y-1 text-xs">
        <div className="flex items-center gap-2">
          <span className="text-primary-500">Speed:</span>
          <span className="font-mono text-primary-700 dark:text-primary-200">
            {d.avg_speed_seconds.toFixed(2)}s
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-primary-500">Accuracy:</span>
          <span className="font-mono text-primary-700 dark:text-primary-200">
            {d.accuracy_pct}%
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-primary-500">Requests:</span>
          <span className="font-mono text-primary-700 dark:text-primary-200">
            {d.total_requests}
          </span>
        </div>
        <div>
          <Badge
            variant={d.batch_type === "sequential" ? "info" : "warning"}
          >
            {d.batch_type}
          </Badge>
        </div>
      </div>
    </div>
  );
}

function BatchLegend({ 
  data, 
  visibleBatches, 
  onToggleBatch 
}: { 
  data: PerformanceStats[]; 
  visibleBatches?: Set<string>; 
  onToggleBatch?: (batchUuid: string) => void;
}) {
  const batches = useMemo(() => {
    const seen = new Set<string>();
    const list: PerformanceStats[] = [];
    for (const d of data) {
      if (!seen.has(d.batch_uuid)) {
        seen.add(d.batch_uuid);
        list.push(d);
      }
    }
    return list;
  }, [data]);

  if (batches.length === 0 || data.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-2 mt-3 justify-center">
      {batches.map((b) => {
        const isVisible = visibleBatches?.has(b.batch_uuid) ?? true;
        return (
          <div
            key={b.batch_uuid}
            onClick={() => onToggleBatch?.(b.batch_uuid)}
            className={`flex items-center gap-1.5 text-xs cursor-pointer select-none transition-opacity ${
              isVisible ? 'opacity-100' : 'opacity-30'
            }`}
            title={`Click to ${isVisible ? 'hide' : 'show'} ${b.friendly_name}`}
          >
            <span
              className="inline-block h-2.5 w-2.5 rounded-sm flex-shrink-0"
              style={{
                backgroundColor: getBatchColor(b.batch_uuid, batches.length),
                border:
                  b.batch_type === "sequential"
                    ? "2px solid currentColor"
                    : "2px dashed currentColor",
              }}
            />
            <span className="text-primary-600 dark:text-primary-300 truncate max-w-[150px]">
              {b.friendly_name} ({b.batch_type})
            </span>
          </div>
        );
      })}
    </div>
  );
}

interface PerformanceChartWithTogglesProps extends PerformanceChartProps {
  visibleBatches?: Set<string>;
  onToggleBatch?: (batchUuid: string) => void;
}

export default function PerformanceChart({
  data,
  visibleBatches,
  onToggleBatch,
}: PerformanceChartWithTogglesProps) {
  const [chartData] = useState<PerformanceStats[]>(data);

  // Clamp X-axis values to 0-200 range
  const chartDataWithKey = useMemo(() => {
    return chartData.map((d, i) => ({
      ...d,
      _key: `${d.batch_uuid}-${d.batch_type}-${i}`,
      clampedSpeed: Math.min(d.avg_speed_seconds, 200),
    }));
  }, [chartData]);

  // Unique batches for color assignment (only visible ones)
  const visibleChartData = useMemo(() => {
    if (!visibleBatches) return chartData;
    return chartData.filter((d) => visibleBatches.has(d.batch_uuid));
  }, [chartData, visibleBatches]);

  const uniqueBatches = useMemo(() => {
    const seen = new Set<string>();
    for (const d of visibleChartData) {
      seen.add(d.batch_uuid);
    }
    return Array.from(seen);
  }, [visibleChartData]);

  // Filter chartDataWithKey by visibleBatches for scatter rendering
  const visibleChartDataWithKey = useMemo(() => {
    if (!visibleBatches) return chartDataWithKey;
    return chartDataWithKey.filter((d) => visibleBatches.has(d.batch_uuid));
  }, [chartDataWithKey, visibleBatches]);

  return (
    <div className="w-full">
      {chartDataWithKey.length === 0 ? (
        <p className="text-center py-12 text-sm text-primary-400">
          No performance data available. Run some tests first.
        </p>
      ) : (
        <>
          {visibleBatches && visibleChartData.length === 0 ? (
            <p className="text-center py-12 text-sm text-primary-400">
              All batches hidden. Click legend items below to show them.
            </p>
          ) : (
            <ScatterChart
              margin={{ top: 20, right: 30, bottom: 30, left: 60 }}
              width="100%"
              height={450}
            >
              <XAxis
                type="number"
                dataKey="clampedSpeed"
                name="Speed"
                label={{
                  value: "Avg Response Time (s)",
                  position: "bottom",
                  offset: 0,
                }}
                domain={[0, 200]}
                tickCount={6}
                tickFormatter={(v) => `${Math.round(v)}s`}
              />
              <YAxis
                type="number"
                dataKey="accuracy_pct"
                name="Accuracy"
                label={{
                  value: "Accuracy %",
                  angle: -90,
                  position: "left",
                }}
                domain={[0, 100]}
                tickCount={6}
              />
              <Tooltip content={<CustomTooltip />} />
              <ReferenceLine y={100} stroke="#aaa" strokeDasharray="3 3" />

              <Scatter
                name="Batches"
                data={visibleChartDataWithKey}
                isAnimationActive={false}
                shape={(props) => {
                  const { cx, cy, payload } = props as { cx: number; cy: number; payload: PerformanceStats };
                  if (cx == null || cy == null) return null;
                  const color = getBatchColor(payload.batch_uuid, uniqueBatches.length);
                  const isSequential = payload.batch_type === "sequential";
                  if (isSequential) {
                    return (
                      <circle
                        cx={cx}
                        cy={cy}
                        r={6}
                        fill={color}
                        stroke={color}
                        strokeWidth={2}
                        style={{ cursor: "pointer" }}
                      />
                    );
                  }
                  // Concurrent: filled circle + dashed outline circle
                  return (
                    <g>
                      <circle
                        cx={cx}
                        cy={cy}
                        r={6}
                        fill={color}
                        stroke="transparent"
                        style={{ cursor: "pointer" }}
                      />
                      <circle
                        cx={cx}
                        cy={cy}
                        r={6}
                        fill="transparent"
                        stroke={color}
                        strokeWidth={2}
                        strokeDasharray="4 3"
                        style={{ cursor: "pointer" }}
                      />
                    </g>
                  );
                }}
              />
            </ScatterChart>
          )}
          <BatchLegend data={chartData} visibleBatches={visibleBatches} onToggleBatch={onToggleBatch} />
          <div className="mt-2 text-center text-xs text-primary-400">
            <span className="inline-flex items-center gap-4">
              <span className="inline-flex items-center gap-1">
                <span className="inline-block h-3 w-3 rounded-sm border-2 border-current" />
                Sequential
              </span>
              <span className="inline-flex items-center gap-1">
                <span
                  className="inline-block h-3 w-3"
                  style={{
                    border: "2px dashed currentColor",
                  }}
                />
                Concurrent
              </span>
            </span>
          </div>
        </>
      )}
    </div>
  );
}
