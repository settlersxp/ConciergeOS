import type { TestMode } from "../../types";
import { Card, FormField, Input } from "../../components/ui";

interface TestConfigCardProps {
  testMode: TestMode;
  batchUuid: string;
  friendlyName: string;
  customerName: string;
  sequentialBatch: number;
  concurrentBatch: number;
  onTestModeChange: (mode: TestMode) => void;
  onBatchUuidChange: (uuid: string) => void;
  onFriendlyNameChange: (name: string) => void;
  onCustomerNameChange: (name: string) => void;
  onSequentialBatchChange: (size: number) => void;
  onConcurrentBatchChange: (size: number) => void;
}

export default function TestConfigCard({
  testMode,
  batchUuid,
  friendlyName,
  customerName,
  sequentialBatch,
  concurrentBatch,
  onTestModeChange,
  onBatchUuidChange,
  onFriendlyNameChange,
  onCustomerNameChange,
  onSequentialBatchChange,
  onConcurrentBatchChange,
}: TestConfigCardProps) {
  const isMulti = testMode === "multi";

  return (
    <Card title="Test Configuration">
      {/* Test Mode */}
      <div className="mb-4">
        <label className="block text-sm font-medium text-primary-700 dark:text-primary-300 mb-2">
          Test Mode
        </label>
        <div className="flex flex-col gap-2">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="radio"
              name="testMode"
              value="single"
              checked={!isMulti}
              onChange={() => onTestModeChange("single")}
              className="h-4 w-4 text-secondary-400 focus:ring-secondary-400"
            />
            <span className="text-sm text-primary-700 dark:text-primary-300">
              Single Guest (all tests same guest)
            </span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="radio"
              name="testMode"
              value="multi"
              checked={isMulti}
              onChange={() => onTestModeChange("multi")}
              className="h-4 w-4 text-secondary-400 focus:ring-secondary-400"
            />
            <span className="text-sm text-primary-700 dark:text-primary-300">
              Multi-Guest (different guest per test)
            </span>
          </label>
        </div>
      </div>

      {/* Multi-Guest Info Banner */}
      {isMulti && (
        <div className="mb-4 px-3 py-2 bg-secondary-50 dark:bg-secondary-900/20 border border-secondary-200 dark:border-secondary-800 rounded-md text-xs text-secondary-600 dark:text-secondary-300">
          <strong>Multi-Guest Mode:</strong> First 5 test guests → Sequential
          batch, last 8 guests → Concurrent batch. Make sure 13 test guests are
          configured below.
        </div>
      )}

      {/* Batch UUID */}
      <div className="mb-4">
        <FormField htmlFor="batchUuid" label="Batch UUID" prefix="(auto-generated)">
          <Input
            id="batchUuid"
            value={batchUuid}
            onChange={(e) => onBatchUuidChange(e.target.value)}
          />
        </FormField>
      </div>

      {/* Friendly Name */}
      <div className="mb-4">
        <FormField htmlFor="friendlyName" label="Friendly Name">
          <Input
            id="friendlyName"
            value={friendlyName}
            onChange={(e) => onFriendlyNameChange(e.target.value)}
          />
        </FormField>
      </div>

      {/* Customer Name (hidden in multi mode) */}
      {!isMulti && (
        <div className="mb-4">
          <FormField htmlFor="customerName" label="Customer Name">
            <Input
              id="customerName"
              value={customerName}
              onChange={(e) => onCustomerNameChange(e.target.value)}
            />
          </FormField>
        </div>
      )}

      {/* Batch Sizes */}
      <div className="grid grid-cols-2 gap-4">
        <FormField htmlFor="sequentialBatch" label="Sequential Requests">
          <Input
            id="sequentialBatch"
            type="number"
            min={1}
            max={50}
            value={sequentialBatch}
            onChange={(e) =>
              onSequentialBatchChange(parseInt(e.target.value) || 1)
            }
          />
        </FormField>
        <FormField htmlFor="concurrentBatch" label="Concurrent Requests">
          <Input
            id="concurrentBatch"
            type="number"
            min={1}
            max={50}
            value={concurrentBatch}
            onChange={(e) =>
              onConcurrentBatchChange(parseInt(e.target.value) || 1)
            }
          />
        </FormField>
      </div>
    </Card>
  );
}