import { useState, useEffect } from 'react';
import { Card, Input, Select, Button, FormField } from './';
import { modelsApi } from '../../services/api';
import type { LLMModel } from '../../types';

interface ModelManagerProps {
  open: boolean;
  onClose: () => void;
  model: LLMModel | null; // null = creating new
  onSave: () => void;
}

const MODEL_TYPE_OPTIONS = [
  { value: 'general', label: 'General' },
  { value: 'text', label: 'Text Generation' },
  { value: 'image_audio', label: 'Image & Audio' },
];

export default function ModelManager({ open, onClose, model, onSave }: ModelManagerProps) {
  const [name, setName] = useState('');
  const [endpoint, setEndpoint] = useState('');
  const [modelsEndpoint, setModelsEndpoint] = useState('');
  const [modelName, setModelName] = useState('');
  const [modelType, setModelType] = useState<'text' | 'image_audio' | 'general'>('general');
  const [vllmVersion, setVllmVersion] = useState('');
  const [thinkingEnabled, setThinkingEnabled] = useState(false);
  const [saving, setSaving] = useState(false);
  const [fetching, setFetching] = useState(false);
  const [fetchStatus, setFetchStatus] = useState('');
  const [error, setError] = useState('');

  // Reset state when modal opens
  useEffect(() => {
    if (open) {
      if (model) {
        // Editing existing model
        setName(model.name);
        setEndpoint(model.endpoint);
        setModelsEndpoint(model.models_endpoint);
        setModelName(model.model_name);
        setModelType(model.model_type as 'text' | 'image_audio' | 'general');
        setVllmVersion(model.vllm_version || '');
        setThinkingEnabled(model.thinking_enabled);
      } else {
        // Creating new model
        setName('');
        setEndpoint('');
        setModelsEndpoint('');
        setModelName('');
        setModelType('general');
        setVllmVersion('');
        setThinkingEnabled(false);
      }
      setError('');
      setFetchStatus('');
    }
  }, [open, model]);

  const handleFetchInfo = async () => {
    setFetching(true);
    setFetchStatus('Fetching model info...');
    try {
      // modelsEndpoint is the /v1/models URL, but we need the raw endpoint for fetch-info
      const baseEndpoint = endpoint.replace(/\/v1\/models$/, '/v1');
      const info = await modelsApi.fetchInfo(baseEndpoint);
      setModelName(info.model_name);
      setVllmVersion(info.vllm_version);
      setThinkingEnabled(info.thinking_enabled);
      setFetchStatus('✓ Model info fetched');
      setTimeout(() => setFetchStatus(''), 3000);
    } catch (err) {
      setFetchStatus('✗ Failed: ' + (err instanceof Error ? err.message : String(err)));
      setTimeout(() => setFetchStatus(''), 5000);
    } finally {
      setFetching(false);
    }
  };

  const normalizeModelsEndpoint = (endpoint: string, baseEndpoint: string): string => {
    let trimmed = endpoint.trim();
    // OpenAI requires /v1/models — always enforce this suffix
    if (trimmed.endsWith('/v1/models')) return trimmed;
    if (trimmed.endsWith('/v1')) return trimmed + '/models';
    // No /v1 suffix → append /v1/models
    const base = trimmed || baseEndpoint.trim().replace(/\/+$/, '');
    if (base.endsWith('/v1')) return base + '/models';
    return base + '/v1/models';
  };

  const handleSave = async () => {
    if (!name.trim()) {
      setError('Friendly name is required');
      return;
    }
    if (!endpoint.trim()) {
      setError('Endpoint is required');
      return;
    }
    if (!modelName.trim()) {
      setError('Model name is required');
      return;
    }

    const normalizedEndpoint = normalizeModelsEndpoint(modelsEndpoint, endpoint);

    setSaving(true);
    setError('');

    try {
      const payload = {
        name: name.trim(),
        endpoint: endpoint.trim(),
        models_endpoint: normalizedEndpoint,
        model_name: modelName.trim(),
        model_type: modelType,
        vllm_version: vllmVersion || undefined,
        thinking_enabled: thinkingEnabled,
      };

      if (model) {
        await modelsApi.update(model.model_id, payload);
      } else {
        await modelsApi.create(payload);
      }
      onSave();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save model');
    } finally {
      setSaving(false);
    }
  };

  if (!open) return null;

  const isEditing = !!model;

  return (
    <>
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
        <Card title={isEditing ? `Edit: ${model?.name}` : 'Add New Model'} className="w-full max-w-lg max-h-[80vh] overflow-y-auto">
          <button
            onClick={onClose}
            className="absolute top-4 right-4 text-primary-500 hover:text-primary-700 dark:text-primary-400 dark:hover:text-white text-2xl leading-none"
          >
            &times;
          </button>

          <div className="space-y-4">
            {/* Friendly Name */}
            <FormField label="Friendly Name" helperText="Human-readable name for this model">
              <Input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., Production Text Model"
                disabled={saving}
              />
            </FormField>

            {/* Model Type */}
            <FormField label="Model Type">
              <Select value={modelType} onChange={(e) => setModelType(e.target.value as 'text' | 'image_audio' | 'general')}>
                {MODEL_TYPE_OPTIONS.map(opt => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </Select>
            </FormField>

            {/* Endpoint */}
            <FormField
              htmlFor="endpoint"
              label="Endpoint"
              helperText="Base URL of the vLLM endpoint (e.g. http://localhost:8000/v1)"
            >
              <Input
                id="endpoint"
                type="text"
                value={endpoint}
                onChange={(e) => setEndpoint(e.target.value)}
                placeholder="http://localhost:8000/v1"
                disabled={saving}
              />
            </FormField>

            {/* Models Endpoint */}
            <FormField
              htmlFor="models_endpoint"
              label="Models Endpoint"
              helperText="Full models endpoint URL (e.g. http://localhost:8000/v1/models)"
            >
              <Input
                id="models_endpoint"
                type="text"
                value={modelsEndpoint}
                onChange={(e) => setModelsEndpoint(e.target.value)}
                placeholder="http://localhost:8000/v1/models"
                disabled={saving}
              />
            </FormField>

            {/* Model Name */}
            <FormField
              htmlFor="model_name"
              label="Model Name"
              helperText="The actual model identifier (e.g. facebook/opt-125m)"
            >
              <Input
                id="model_name"
                type="text"
                value={modelName}
                onChange={(e) => setModelName(e.target.value)}
                placeholder="facebook/opt-125m"
                disabled={saving}
              />
            </FormField>

            {/* Fetch Model Info */}
            <div className="flex items-center gap-3">
              <Button
                variant="secondary"
                loading={fetching}
                onClick={handleFetchInfo}
                disabled={!endpoint.trim()}
              >
                Fetch Model Info
              </Button>
              {fetchStatus && (
                <span className={`text-xs ${fetchStatus.startsWith('✗') ? 'text-accent-400' : 'text-primary-400 dark:text-primary-500'}`}>
                  {fetchStatus}
                </span>
              )}
            </div>

            {/* vLLM Version */}
            <FormField label="vLLM Version">
              <Input
                type="text"
                value={vllmVersion}
                onChange={(e) => setVllmVersion(e.target.value)}
                placeholder="e.g., 0.6.0"
                disabled={saving}
              />
            </FormField>

            {/* Thinking Enabled */}
            <div className="flex items-center gap-2">
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
          </div>

          {error && (
            <div className="mt-4 rounded-md bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 px-3 py-2 text-sm text-red-700 dark:text-red-400">
              {error}
            </div>
          )}

          <div className="flex justify-end gap-2 mt-6">
            <Button onClick={onClose} disabled={saving} variant="ghost">
              Cancel
            </Button>
            <Button onClick={handleSave} disabled={saving} variant="primary" loading={saving}>
              {isEditing ? 'Save Changes' : 'Add Model'}
            </Button>
          </div>
        </Card>
      </div>
    </>
  );
}