import { useEffect, useRef, useState } from 'react';
import { settingsApi } from '../services/api';
import type { AppSettings, TestSettings } from '../types';
import { PageHeader, Card, FormField, Input, Select, Button, Toast } from '../components/ui';

export default function Settings() {
  // Form state
  const [modelsEndpoint, setModelsEndpoint] = useState('');
  const [modelName, setModelName] = useState('');
  const [vllmVersion, setVllmVersion] = useState('');
  const [thinkingEnabled, setThinkingEnabled] = useState(false);
  const [expectedFormat, setExpectedFormat] = useState('auto');
  const [responseCacheEnabled, setResponseCacheEnabled] = useState(true);

  // UI state
  const [saving, setSaving] = useState(false);
  const [fetching, setFetching] = useState(false);
  const [fetchStatus, setFetchStatus] = useState('');
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'info' } | null>(null);

  // Load settings on mount
  useEffect(() => {
    settingsApi.get().then((data) => {
      const ts = data.test_settings;
      if (ts) {
        setModelsEndpoint(ts.models_endpoint ?? '');
        setModelName(ts.model_name ?? '');
        setVllmVersion(ts.vllm_version ?? '');
        setThinkingEnabled(ts.thinking_enabled ?? false);
        setExpectedFormat(ts.expected_format ?? 'auto');
        setResponseCacheEnabled(ts.response_cache_enabled ?? true);
      }
    });
  }, []);

  const handleSave = async () => {
    setSaving(true);
    const payload: AppSettings = {
      test_settings: {
        models_endpoint: modelsEndpoint,
        model_name: modelName,
        vllm_version: vllmVersion,
        thinking_enabled: thinkingEnabled,
        expected_format: expectedFormat,
        response_cache_enabled: responseCacheEnabled,
      } satisfies TestSettings,
    };

    try {
      await settingsApi.update(payload);
      setToast({ message: 'Settings saved successfully', type: 'success' });
    } catch (err: unknown) {
      setToast({ message: err instanceof Error ? err.message : 'Failed to save settings', type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  const modelsEndpointRef = useRef<HTMLInputElement>(null);

  const handleFetchModelInfo = async () => {
    setFetching(true);
    setFetchStatus('Connecting to models endpoint...');

    try {
      const endpoint = modelsEndpointRef.current?.value?.trim() ?? '';

      const resp = await fetch(endpoint);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      const models = data.data ?? [];
      if (!models.length) throw new Error('No models found');

      const m = models[0];
      setModelName(m.id ?? m.model ?? 'unknown');

      let version = m.vllm_version ?? '';
      if (!version && m.extra && typeof m.extra === 'object') {
        version = m.extra.vllm_version ?? 'unknown';
      }
      setVllmVersion(version || 'unknown');

      let thinking = false;
      if (m.capabilities && typeof m.capabilities === 'object') {
        thinking = m.capabilities.thinking ?? false;
      }
      const mtype = String(m.type ?? '');
      if (mtype.toLowerCase().includes('thinking')) thinking = true;
      setThinkingEnabled(thinking);

      setFetchStatus('✓ Model info fetched successfully');
      setTimeout(() => setFetchStatus(''), 3000);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setFetchStatus('✗ Failed: ' + msg);
      setTimeout(() => setFetchStatus(''), 5000);
    } finally {
      setFetching(false);
    }
  };

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <PageHeader
        title="Model Settings"
        description="Configure global LLM parameters for the application and performance testing."
      />

      <form onSubmit={(e: React.FormEvent) => e.preventDefault()}>
        {/* vLLM Connection */}
        <Card title="vLLM Connection" className="mb-6">
          <div className="mt-4">
            <FormField
              htmlFor="models_endpoint"
              label="Models Endpoint"
              helperText="Example: http://localhost:8000/v1/models (base URL + /models)"
            >
              <Input
                ref={modelsEndpointRef}
                id="models_endpoint"
                type="text"
                value={modelsEndpoint}
                onChange={(e) => setModelsEndpoint(e.target.value)}
              />
            </FormField>
          </div>

          <div className="mt-4">
            <FormField htmlFor="model_name" label="Model Name">
              <Input
                id="model_name"
                type="text"
                value={modelName}
                onChange={(e) => setModelName(e.target.value)}
              />
            </FormField>
          </div>

          <div className="mt-4 flex items-center gap-3">
            <Button variant="secondary" loading={fetching} onClick={handleFetchModelInfo}>
              Fetch Model Info
            </Button>
            {fetchStatus && (
              <span className={`text-xs ${fetchStatus.startsWith('✗') ? 'text-accent-400' : 'text-primary-400 dark:text-primary-500'}`}>
                {fetchStatus}
              </span>
            )}
          </div>
        </Card>

        {/* Model Information */}
        <Card title="Model Information" className="mb-6">
          <div className="mt-4">
            <FormField htmlFor="vllm_version" label="vLLM Version">
              <Input
                id="vllm_version"
                type="text"
                value={vllmVersion}
                onChange={(e) => setVllmVersion(e.target.value)}
                placeholder="e.g. 0.6.0"
              />
            </FormField>
          </div>

          <div className="mt-4 flex items-center gap-2">
            <input
              id="thinking_enabled"
              type="checkbox"
              checked={thinkingEnabled}
              onChange={(e) => setThinkingEnabled(e.target.checked)}
              className="h-4 w-4 rounded border-surface-300 text-secondary-400 focus:ring-secondary-400 dark:border-primary-600"
            />
            <label htmlFor="thinking_enabled" className="text-sm text-primary-700 dark:text-primary-300">
              Thinking Enabled
            </label>
          </div>

          <div className="mt-4">
            <FormField htmlFor="expected_format" label="Expected Response Format">
              <Select
                id="expected_format"
                value={expectedFormat}
                onChange={(e) => setExpectedFormat(e.target.value)}
              >
                <option value="auto">Auto-Detect</option>
                <option value="json">JSON</option>
                <option value="text">TEXT</option>
              </Select>
            </FormField>
          </div>
        </Card>

        {/* Response Cache */}
        <Card title="Response Cache" className="mb-6">
          <div className="mt-4 flex items-center gap-2">
            <input
              id="response_cache_enabled"
              type="checkbox"
              checked={responseCacheEnabled}
              onChange={(e) => setResponseCacheEnabled(e.target.checked)}
              className="h-4 w-4 rounded border-surface-300 text-secondary-400 focus:ring-secondary-400 dark:border-primary-600"
            />
            <label htmlFor="response_cache_enabled" className="text-sm text-primary-700 dark:text-primary-300">
              Enable Response Cache
            </label>
          </div>
          <p className="mt-2 text-xs text-primary-600 dark:text-primary-400">
            When enabled, LLM responses are cached by customer name to avoid redundant API calls. 
            Disabling this allows real-time testing of all queries without cache interference.
          </p>
        </Card>

        {/* Save button */}
        <div className="flex justify-end">
          <Button variant="primary" size="lg" loading={saving} onClick={handleSave}>
            Save Changes
          </Button>
        </div>
      </form>

      {/* Toast */}
      {toast && (
        <Toast message={toast.message} type={toast.type} onHidden={() => setToast(null)} />
      )}
    </div>
  );
}