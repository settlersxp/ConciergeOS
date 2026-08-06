import React from 'react';

interface TestConfigFormProps {
  customerName: string;
  vllmUrl: string;
  modelsEndpoint: string;
  model: string;
  testMode: 'single' | 'multi';
  dataFormat: string;
  sequentialBatch: number;
  concurrentBatch: number;
  friendlyName: string;
  thinkingEnabled: boolean;
  systemPrompt: string;
  userPrompt: string;
  expectedFormat: string;
  running: boolean;
  onCustomerNameChange: (value: string) => void;
  onVllmUrlChange: (value: string) => void;
  onModelsEndpointChange: (value: string) => void;
  onModelChange: (value: string) => void;
  onTestModeChange: (value: 'single' | 'multi') => void;
  onDataFormatChange: (value: string) => void;
  onSequentialBatchChange: (value: number) => void;
  onConcurrentBatchChange: (value: number) => void;
  onFriendlyNameChange: (value: string) => void;
  onThinkingEnabledChange: (value: boolean) => void;
  onSystemPromptChange: (value: string) => void;
  onUserPromptChange: (value: string) => void;
  onExpectedFormatChange: (value: string) => void;
  onRun: () => void;
  onSetupGuests: () => void;
  onGenerateData: () => void;
}

export const TestConfigForm: React.FC<TestConfigFormProps> = ({
  customerName,
  vllmUrl,
  modelsEndpoint,
  model,
  testMode,
  dataFormat,
  sequentialBatch,
  concurrentBatch,
  friendlyName,
  thinkingEnabled,
  systemPrompt,
  userPrompt,
  expectedFormat,
  running,
  onCustomerNameChange,
  onVllmUrlChange,
  onModelsEndpointChange,
  onModelChange,
  onTestModeChange,
  onDataFormatChange,
  onSequentialBatchChange,
  onConcurrentBatchChange,
  onFriendlyNameChange,
  onThinkingEnabledChange,
  onSystemPromptChange,
  onUserPromptChange,
  onExpectedFormatChange,
  onRun,
  onSetupGuests,
  onGenerateData,
}) => {
  return (
    <div className="mb-8 grid gap-4 rounded-lg border border-gray-200 bg-white p-6 shadow-sm md:grid-cols-2">
      <div>
        <label className="mb-1 block text-xs font-medium text-gray-500">Customer Name</label>
        <input value={customerName} onChange={(e) => onCustomerNameChange(e.target.value)}
          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500" />
      </div>
      <div>
        <label className="mb-1 block text-xs font-medium text-gray-500">Model</label>
        <input value={model} onChange={(e) => onModelChange(e.target.value)} placeholder="Model name"
          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500" />
      </div>
      <div>
        <label className="mb-1 block text-xs font-medium text-gray-500">vLLM URL</label>
        <input value={vllmUrl} onChange={(e) => onVllmUrlChange(e.target.value)}
          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500" />
      </div>
      <div>
        <label className="mb-1 block text-xs font-medium text-gray-500">Models Endpoint</label>
        <input value={modelsEndpoint} onChange={(e) => onModelsEndpointChange(e.target.value)}
          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500" />
      </div>
      <div>
        <label className="mb-1 block text-xs font-medium text-gray-500">Friendly Name</label>
        <input value={friendlyName} onChange={(e) => onFriendlyNameChange(e.target.value)} placeholder="Optional"
          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500" />
      </div>
      <div>
        <label className="mb-1 block text-xs font-medium text-gray-500">Test Mode</label>
        <select value={testMode} onChange={(e) => onTestModeChange(e.target.value as 'single' | 'multi')}
          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500">
          <option value="single">Single</option>
          <option value="multi">Multi-guest</option>
        </select>
      </div>
      <div>
        <label className="mb-1 block text-xs font-medium text-gray-500">Data Format</label>
        <select value={dataFormat} onChange={(e) => onDataFormatChange(e.target.value)}
          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500">
          <option value="csv">CSV</option>
          <option value="json">JSON</option>
          <option value="xml">XML</option>
          <option value="tool_calling">Tool Calling</option>
        </select>
      </div>
      <div>
        <label className="mb-1 block text-xs font-medium text-gray-500">Expected Format</label>
        <select value={expectedFormat} onChange={(e) => onExpectedFormatChange(e.target.value)}
          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500">
          <option value="auto">Auto</option>
          <option value="json">JSON</option>
          <option value="text">Text</option>
        </select>
      </div>
      <div>
        <label className="mb-1 block text-xs font-medium text-gray-500">Sequential Batch</label>
        <input type="number" value={sequentialBatch} onChange={(e) => onSequentialBatchChange(Number(e.target.value))}
          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500" />
      </div>
      <div>
        <label className="mb-1 block text-xs font-medium text-gray-500">Concurrent Batch</label>
        <input type="number" value={concurrentBatch} onChange={(e) => onConcurrentBatchChange(Number(e.target.value))}
          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500" />
      </div>
      <div className="flex items-center gap-2 pt-6">
        <input type="checkbox" id="thinking" checked={thinkingEnabled} onChange={(e) => onThinkingEnabledChange(e.target.checked)}
          className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
        <label htmlFor="thinking" className="text-sm text-gray-700">Thinking Enabled</label>
      </div>
      <div className="flex gap-2 pt-6">
        <button onClick={onSetupGuests}
          className="rounded-md bg-gray-600 px-4 py-2 text-sm text-white hover:bg-gray-700 transition-colors">
          Setup Guests
        </button>
        <button onClick={onGenerateData}
          className="rounded-md bg-gray-600 px-4 py-2 text-sm text-white hover:bg-gray-700 transition-colors">
          Generate Data
        </button>
      </div>
      <div className="md:col-span-2">
        <label className="mb-1 block text-xs font-medium text-gray-500">System Prompt</label>
        <textarea value={systemPrompt} onChange={(e) => onSystemPromptChange(e.target.value)} rows={3} placeholder="Leave empty for default"
          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500" />
      </div>
      <div className="md:col-span-2">
        <label className="mb-1 block text-xs font-medium text-gray-500">User Prompt</label>
        <textarea value={userPrompt} onChange={(e) => onUserPromptChange(e.target.value)} rows={2}
          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500" />
      </div>
      <div className="md:col-span-2">
        <button onClick={onRun} disabled={running}
          className="w-full rounded-md bg-blue-600 px-4 py-3 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 transition-colors">
          {running ? 'Running...' : 'Run Performance Test'}
        </button>
      </div>
    </div>
  );
};