import { useEffect, useRef, useState } from 'react';
import { useSettings } from '../context/SettingsContext';
import type { AppSettings, TestSettings } from '../types';
import { PageHeader, Card, FormField, Input, Select, Button, Toast } from '../components/ui';

export default function Settings() {
  const {
    modelsEndpoint,
    modelName,
    vllmVersion,
    thinkingEnabled,
    expectedFormat,
    saveSettings,
  } = useSettings();

  // Local edit state (may differ from saved until user clicks Save)
  const [editEndpoint, setEditEndpoint] = useState(modelsEndpoint);
  const [editModelName, setEditModelName] = useState(modelName);
  const [editVllmVersion, setEditVllmVersion] = useState(vllmVersion);
  const [editThinkingEnabled, setEditThinkingEnabled] = useState(thinkingEnabled);
  const [editExpectedFormat, setEditExpectedFormat] = useState(expectedFormat);

  // Sync local edit state when context changes (e.g., after save from another page)
  useEffect(() => {
    setEditEndpoint(modelsEndpoint);
    setEditModelName(modelName);
    setEditVllmVersion(vllmVersion);
    setEditThinkingEnabled(thinkingEnabled);
    setEditExpectedFormat(expectedFormat);
  }, [modelsEndpoint, modelName, vllmVersion, thinkingEnabled, expectedFormat]);

  // UI state
  const [saving, setSaving] = useState(false);
  const [fetching, setFetching] = useState(false);
  const [fetchStatus, setFetchStatus] = useState('');
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'info' } | null>(null);

  const handleSave = async () => {
    setSaving(true);
    const payload: AppSettings = {
      test_settings: {
        models_endpoint: editEndpoint,
        model_name: editModelName,
        vllm_version: editVllmVersion,
        thinking_enabled: editThinkingEnabled,
        expected_format: editExpectedFormat,
      } satisfies TestSettings,
    };

    try {
      await saveSettings(payload);
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
      setEditModelName(m.id ?? m.model ?? 'unknown');

      let version = m.vllm_version ?? '';
      if (!version && m.extra && typeof m.extra === 'object') {
        version = m.extra.vllm_version ?? 'unknown';
      }
      setEditVllmVersion(version || 'unknown');

      let thinking = false;
      if (m.capabilities && typeof m.capabilities === 'object') {
        thinking = m.capabilities.thinking ?? false;
      }
      const mtype = String(m.type ?? '');
      if (mtype.toLowerCase().includes('thinking')) thinking = true;
      setEditThinkingEnabled(thinking);

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
                value={editEndpoint}
                onChange={(e) => setEditEndpoint(e.target.value)}
              />
            </FormField>
          </div>

          <div className="mt-4">
            <FormField htmlFor="model_name" label="Model Name">
              <Input
                id="model_name"
                type="text"
                value={editModelName}
                onChange={(e) => setEditModelName(e.target.value)}
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
                value={editVllmVersion}
                onChange={(e) => setEditVllmVersion(e.target.value)}
                placeholder="e.g. 0.6.0"
              />
            </FormField>
          </div>

          <div className="mt-4 flex items-center gap-2">
            <input
              id="thinking_enabled"
              type="checkbox"
              checked={editThinkingEnabled}
              onChange={(e) => setEditThinkingEnabled(e.target.checked)}
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
                value={editExpectedFormat}
                onChange={(e) => setEditExpectedFormat(e.target.value)}
              >
                <option value="auto">Auto-Detect</option>
                <option value="json">JSON</option>
                <option value="text">TEXT</option>
              </Select>
            </FormField>
          </div>
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