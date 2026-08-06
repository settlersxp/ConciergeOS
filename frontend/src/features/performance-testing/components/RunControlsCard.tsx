import type { ChangeEvent } from "react";
import type { Batch } from "../../types";
import { Card, Button, Select } from "../../components/ui";

interface RunControlsCardProps {
  batches: Batch[];
  selectedBatchUuid: string;
  compareCount: number;
  running: boolean;
  onRun: () => void;
  onGenerateData: () => void;
  onLoadLatest: () => void;
  onLoadAll: () => void;
  onLoadBatch: () => void;
  onDeleteBatch: () => void;
  onCompare: () => void;
  onBatchSelectChange: (uuid: string) => void;
}

export default function RunControlsCard({
  batches,
  selectedBatchUuid,
  compareCount,
  running,
  onRun,
  onGenerateData,
  onLoadLatest,
  onLoadAll,
  onLoadBatch,
  onDeleteBatch,
  onCompare,
  onBatchSelectChange,
}: RunControlsCardProps) {
  return (
    <Card title="Run Controls">
      <div className="flex flex-wrap gap-3">
        <Button variant="primary" loading={running} onClick={onRun}>
          Run Tests
        </Button>
        <Button variant="secondary" onClick={onGenerateData}>
          Generate Data
        </Button>
        <Button variant="secondary" onClick={onLoadLatest}>
          Load Latest
        </Button>
        <Button variant="secondary" onClick={onLoadAll}>
          Load All
        </Button>
      </div>

      <div className="mt-4 flex flex-wrap items-end gap-3">
        <div className="min-w-[240px]">
          <label className="mb-1 block text-sm font-medium text-primary-700 dark:text-primary-300">
            Load by Batch
          </label>
          <Select
            value={selectedBatchUuid}
            onChange={(e: ChangeEvent<HTMLSelectElement>) => onBatchSelectChange(e.target.value)}
          >
            <option value="">-- Select batch --</option>
            {batches.map((b) => (
              <option key={b.batch_uuid} value={b.batch_uuid}>
                {b.friendly_name || b.batch_uuid.substring(0, 8)} ({b.total_requests} tests)
              </option>
            ))}
          </Select>
        </div>

        <Button variant="secondary" onClick={onLoadBatch}>
          Load Batch
        </Button>
        <Button variant="danger" onClick={onDeleteBatch}>
          Delete Batch
        </Button>
        <Button
          variant="secondary"
          disabled={compareCount !== 2}
          onClick={onCompare}
        >
          Compare ({compareCount}/2)
        </Button>
      </div>
    </Card>
  );
}