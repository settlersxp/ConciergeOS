import { useEffect, useState, useCallback } from "react";
import { performanceApi, settingsApi } from "../services/api";
import type {
  TestResult,
  Batch,
  TestGuest,
  PerformanceTestRequest,
  TestMode,
  DataFormat,
  StatusType,
  SummaryData,
} from "../types";
import { PageHeader } from "../components/ui";

import TestConfigCard from "./components/TestConfigCard";
import GuestConfigCard from "./components/GuestConfigCard";
import PromptSettingsCard from "./components/PromptSettingsCard";
import DataFormatCard from "./components/DataFormatCard";
import RunControlsCard from "./components/RunControlsCard";
import StatusBanner from "./components/StatusBanner";
import SummaryCards from "./components/SummaryCards";
import ResultsList from "./components/ResultsList";
import CompareModal from "./components/CompareModal";

function generateUuid(): string {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

function computeSummary(rows: TestResult[]): SummaryData {
  const times = rows.map((r) => {
    const sent = new Date(r.request_sent_time);
    const received = new Date(r.response_received_time);
    return (received.getTime() - sent.getTime()) / 1000;
  });
  const avg = times.length
    ? (times.reduce((a, b) => a + b, 0) / times.length).toFixed(2)
    : "0";
  const min = times.length ? Math.min(...times).toFixed(2) : "0";
  const max = times.length ? Math.max(...times).toFixed(2) : "0";
  const model = rows.length > 0 ? rows[0].model_name : undefined;

  return { total: rows.length, avg, min, max, model };
}

export default function PerformanceTesting() {
  // Form state
  const [customerName, setCustomerName] = useState("عائشة إبراهيم");
  const [testMode, setTestMode] = useState<TestMode>("single");
  const [dataFormat, setDataFormat] = useState<DataFormat>("csv");
  const [sequentialBatch, setSequentialBatch] = useState(5);
  const [concurrentBatch, setConcurrentBatch] = useState(8);
  const [friendlyName, setFriendlyName] = useState("");
  const [batchUuid, setBatchUuid] = useState(generateUuid());
  const [systemPrompt, setSystemPrompt] = useState("");
  const [userPrompt, setUserPrompt] = useState("");

  // Settings from API (model info, etc.)
  const [modelName, setModelName] = useState("");
  const [vllmUrl, setVllmUrl] = useState("");
  const [modelsEndpoint, setModelsEndpoint] = useState("");
  const [thinkingEnabled, setThinkingEnabled] = useState(false);

  // Results & misc
  const [running, setRunning] = useState(false);
  const [guestLoading, setGuestLoading] = useState(false);
  const [status, setStatus] = useState<{ message: string; type: StatusType } | null>(null);
  const [results, setResults] = useState<TestResult[]>([]);
  const [batches, setBatches] = useState<Batch[]>([]);
  const [testGuests, setTestGuests] = useState<TestGuest[]>([]);
  const [selectedBatchUuid, setSelectedBatchUuid] = useState("");
  const [selectedForCompare, setSelectedForCompare] = useState<TestResult[]>([]);
  const [compareModalOpen, setCompareModalOpen] = useState(false);

  // Load batches on mount
  useEffect(() => {
    loadBatches();
    loadGuests();
    loadAppSettings();
  }, []);

  const loadBatches = async () => {
    try {
      const data = await performanceApi.getBatches();
      setBatches(data);
    } catch {
      /* ignore */
    }
  };

  const loadGuests = async () => {
    try {
      const data = await performanceApi.getTestGuests();
      setTestGuests(data);
      // Auto-fill customer name with first guest
      if (data.length > 0 && !customerName) {
        setCustomerName(data[0].full_name);
      }
    } catch {
      /* ignore */
    }
  };

  const loadAppSettings = async () => {
    try {
      const data = await settingsApi.get();
      const ts = data.test_settings;
      if (ts) {
        setModelName(ts.model_name || "");
        setThinkingEnabled(ts.thinking_enabled || false);
        setModelsEndpoint(ts.models_endpoint || "");
        // Derive vllm_url from models_endpoint
        if (ts.models_endpoint) {
          setVllmUrl(
            ts.models_endpoint.replace("/models", "").replace("/v1/models", "")
          );
        }
        // Set friendly name if empty
        if (ts.model_name && !friendlyName) {
          setFriendlyName(ts.model_name);
        }
      }
    } catch {
      /* ignore */
    }
  };

  const handleRun = async () => {
    setRunning(true);
    setStatus({ message: "Running performance tests... This may take a while.", type: "running" });

    const payload: PerformanceTestRequest = {
      customer_name: customerName,
      vllm_url: vllmUrl,
      models_endpoint: modelsEndpoint,
      model_name: modelName,
      sequential_batch_size: sequentialBatch,
      concurrent_batch_size: concurrentBatch,
      test_mode: testMode,
      friendly_name: friendlyName,
      thinking_enabled: thinkingEnabled,
      system_prompt: systemPrompt,
      user_prompt: userPrompt,
      expected_response_format: "auto",
      data_format: dataFormat,
      batch_uuid: batchUuid,
    };

    try {
      const data = await performanceApi.runTest(payload);
      const label =
        (data as Record<string, unknown>).friendly_name ||
        `UUID ${(data as Record<string, unknown>).batch_uuid?.toString()?.substring(0, 8)}`;
      const total = (data as Record<string, unknown>).total_requests ?? "?";
      const runId = (data as Record<string, unknown>).run_id ?? "?";
      setStatus({
        message: `Tests completed! Run #${runId} (${label}) — ${total} requests total.`,
        type: "success",
      });

      // Load the results for the batch just run
      const batchUuidRun = (data as Record<string, unknown>).batch_uuid as string;
      if (batchUuidRun) {
        const resultsData = await performanceApi.getResultsByBatch(batchUuidRun);
        setResults(resultsData);
      }

      await loadBatches();
      // Generate new UUID for next run
      setBatchUuid(generateUuid());
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setStatus({ message: `Error running tests: ${msg}`, type: "error" });
    } finally {
      setRunning(false);
    }
  };

  const handleLoadLatest = async () => {
    setStatus({ message: "Loading latest results...", type: "running" });
    try {
      const data = await performanceApi.getResults();
      if (!data.length) {
        setStatus({ message: "No results found in database.", type: "error" });
        return;
      }
      setResults(data);
      setStatus({
        message: `Results loaded successfully. ${data.length} records retrieved (latest 100).`,
        type: "success",
      });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setStatus({ message: `Error loading results: ${msg}`, type: "error" });
    }
  };

  const handleLoadAll = async () => {
    setStatus({ message: "Loading all results from database...", type: "running" });
    try {
      const data = await performanceApi.getAllResults();
      if (!data.length) {
        setStatus({ message: "No results found in database.", type: "error" });
        return;
      }
      setResults(data);
      setSelectedForCompare([]);
      setStatus({
        message: `All results loaded successfully. ${data.length} records retrieved.`,
        type: "success",
      });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setStatus({ message: `Error loading all results: ${msg}`, type: "error" });
    }
  };

  const handleLoadBatch = async () => {
    const batchUuid = String(selectedBatchUuid).trim();
    if (!batchUuid) {
      setStatus({ message: "Please select a batch from the dropdown.", type: "error" });
      return;
    }
    setStatus({ message: "Loading batch results...", type: "running" });
    try {
      const data = await performanceApi.getResultsByBatch(batchUuid);
      if (!data.length) {
        setStatus({ message: "No results found for selected batch.", type: "error" });
        return;
      }
      setResults(data);
      setSelectedForCompare([]);
      const fn = data[0].friendly_name || batchUuid.substring(0, 8);
      setStatus({
        message: `Batch "${fn}" loaded. ${data.length} records retrieved.`,
        type: "success",
      });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setStatus({ message: `Error loading batch: ${msg}`, type: "error" });
    }
  };

  const handleDeleteBatch = async () => {
    if (!selectedBatchUuid) {
      setStatus({ message: "Please select a batch to delete.", type: "error" });
      return;
    }

    if (
      !confirm(
        "Are you sure you want to delete this batch? This action cannot be undone."
      )
    ) {
      return;
    }

    setStatus({ message: "Deleting batch...", type: "running" });
    try {
      const data = await performanceApi.deleteBatch(selectedBatchUuid);
      const deleted =
        (data as Record<string, unknown>).deleted_count ?? "some";
      setStatus({
        message: `Batch deleted successfully. ${deleted} records removed.`,
        type: "success",
      });
      setResults([]);
      setSelectedForCompare([]);
      setSelectedBatchUuid("");
      await loadBatches();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setStatus({ message: `Error deleting batch: ${msg}`, type: "error" });
    }
  };

  const handleToggleValid = async (id: number, valid: boolean) => {
    try {
      await performanceApi.updateValidResponse(id, valid);
      // Update local state
      setResults((prev) =>
        prev.map((r) => (r.id === id ? { ...r, valid_response: valid } : r))
      );
      // Update comparison selection if result is selected
      setSelectedForCompare((prev) =>
        prev.map((r) => (r.id === id ? { ...r, valid_response: valid } : r))
      );
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setStatus({ message: `Error updating result: ${msg}`, type: "error" });
    }
  };

  const handleSetupGuests = async () => {
    setGuestLoading(true);
    setStatus({
      message: "Creating 13 test guests with 4 reservations each...",
      type: "running",
    });
    try {
      const data = await performanceApi.setupGuests();
      if (data.ok) {
        setTestGuests(data.guests);
        setStatus({
          message: `✅ ${data.total} test guests created successfully! (4 reservations each = ${data.total * 4} total reservations)`,
          type: "success",
        });
      } else {
        setStatus({
          message: `Setup failed: ${(data as Record<string, unknown>).error}`,
          type: "error",
        });
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setStatus({ message: `Error setting up guests: ${msg}`, type: "error" });
    } finally {
      setGuestLoading(false);
    }
  };

  const handleGenerateData = async () => {
    setStatus({
      message: "Generating all data files (CSV, JSON, XML)...",
      type: "running",
    });
    try {
      const data = await performanceApi.generateAll();
      if (data.ok) {
        setStatus({
          message: "All data files generated successfully!",
          type: "success",
        });
      } else {
        setStatus({
          message: `Generation failed: ${(data as Record<string, unknown>).error}`,
          type: "error",
        });
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setStatus({ message: `Error generating data: ${msg}`, type: "error" });
    }
  };

  const handleToggleCompare = useCallback(
    (result: TestResult) => {
      setSelectedForCompare((prev) => {
        const exists = prev.find((r) => r.id === result.id);
        if (exists) {
          return prev.filter((r) => r.id !== result.id);
        }
        if (prev.length >= 2) {
          // Remove the first one to make room
          const withoutFirst = prev.slice(1);
          return [...withoutFirst, result];
        }
        return [...prev, result];
      });
    },
    [],
  );

  const handleOpenCompare = () => {
    if (selectedForCompare.length === 2) {
      setCompareModalOpen(true);
    }
  };

  const handleCompareClose = () => {
    setCompareModalOpen(false);
  };

  const summaryData = computeSummary(results);
  const hasResults = results.length > 0;

  return (
    <div className="mx-auto max-w-[95vw] px-6 py-8">
      <PageHeader title="Performance Testing" />

      {/* Status Banner */}
      {status && (
        <StatusBanner message={status.message} type={status.type} />
      )}

      {/* Card Grid */}
      <div className="grid gap-6 md:grid-cols-2 mb-6">
        <TestConfigCard
          testMode={testMode}
          batchUuid={batchUuid}
          friendlyName={friendlyName}
          customerName={customerName}
          sequentialBatch={sequentialBatch}
          concurrentBatch={concurrentBatch}
          onTestModeChange={setTestMode}
          onBatchUuidChange={setBatchUuid}
          onFriendlyNameChange={setFriendlyName}
          onCustomerNameChange={setCustomerName}
          onSequentialBatchChange={setSequentialBatch}
          onConcurrentBatchChange={setConcurrentBatch}
        />

        <GuestConfigCard
          guests={testGuests}
          sequentialBatchSize={sequentialBatch}
          loading={guestLoading}
          onSetupGuests={handleSetupGuests}
          onRefreshList={loadGuests}
        />
      </div>

      {/* Full-width cards */}
      <div className="grid gap-6 md:grid-cols-2 mb-6">
        <PromptSettingsCard
          systemPrompt={systemPrompt}
          userPrompt={userPrompt}
          onSystemPromptChange={setSystemPrompt}
          onUserPromptChange={setUserPrompt}
        />

        <DataFormatCard
          dataFormat={dataFormat}
          onDataFormatChange={setDataFormat}
        />
      </div>

      {/* Run Controls */}
      <div className="mb-6">
        <RunControlsCard
          batches={batches}
          selectedBatchUuid={selectedBatchUuid}
          compareCount={selectedForCompare.length}
          running={running}
          onRun={handleRun}
          onGenerateData={handleGenerateData}
          onLoadLatest={handleLoadLatest}
          onLoadAll={handleLoadAll}
          onLoadBatch={handleLoadBatch}
          onDeleteBatch={handleDeleteBatch}
          onCompare={handleOpenCompare}
          onBatchSelectChange={setSelectedBatchUuid}
        />
      </div>

      {/* Results Section */}
      {hasResults && (
        <div className="mt-8">
          <h3 className="mb-4 text-xl font-semibold text-primary-900 dark:text-white">
            Results — Run{' '}
            <span className="text-primary-600 dark:text-primary-300">
              {[...new Set(results.map((r) => r.run_id))].join(", ")}
            </span>
          </h3>

          <SummaryCards data={summaryData} />

          <ResultsList
            results={results}
            selectedForCompare={selectedForCompare}
            onToggleCompare={handleToggleCompare}
            onToggleValid={handleToggleValid}
          />
        </div>
      )}

      {/* Comparison Modal */}
      {compareModalOpen && selectedForCompare.length === 2 && (
        <CompareModal
          resultA={selectedForCompare[0]}
          resultB={selectedForCompare[1]}
          onClose={handleCompareClose}
          onToggleValid={handleToggleValid}
        />
      )}
    </div>
  );
}