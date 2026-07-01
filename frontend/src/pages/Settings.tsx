import { useEffect, useState } from 'react';
import { modelsApi } from '../services/api';
import type { LLMModel } from '../types';
import { PageHeader, Card, Button, Toast } from '../components/ui';
import ModelManager from '../components/ui/ModelManager';

export default function Settings() {
  const [models, setModels] = useState<LLMModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingModel, setEditingModel] = useState<LLMModel | null>(null);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'info' } | null>(null);

  useEffect(() => {
    loadModels();
  }, []);

  const loadModels = async () => {
    setLoading(true);
    try {
      console.log('[Settings] Fetching models from /api/models...');
      const data = await modelsApi.getAll();
      console.log('[Settings] Received models response:', data);
      console.log('[Settings] Response is array:', Array.isArray(data), 'length:', Array.isArray(data) ? data.length : 'N/A');
      setModels(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('[Settings] Failed to load models:', err);
      setModels([]);
      setToast({ message: err instanceof Error ? err.message : 'Failed to load models', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const handleAdd = () => {
    setEditingModel(null);
    setModalOpen(true);
  };

  const handleEdit = (model: LLMModel) => {
    setEditingModel(model);
    setModalOpen(true);
  };

  const handleDelete = async (modelId: number) => {
    if (!confirm('Delete this model?')) return;
    try {
      await modelsApi.delete(modelId);
      await loadModels();
      setToast({ message: 'Model deleted', type: 'success' });
    } catch (err) {
      setToast({ message: err instanceof Error ? err.message : 'Delete failed', type: 'error' });
    }
  };

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <PageHeader
        title="LLM Models"
        description="Manage your configured LLM models. Each model can be assigned to one or more prompts."
      />

      <Card title="Configured Models" className="mb-6">
        <div className="mt-4 flex justify-end">
          <Button variant="primary" onClick={handleAdd}>
            + Add Model
          </Button>
        </div>

        {loading ? (
          <div className="mt-4 text-sm text-primary-500">Loading models...</div>
        ) : models.length === 0 ? (
          <div className="mt-4 text-sm text-primary-500">
            No models configured. Click "Add Model" to get started.
          </div>
        ) : (
          <div className="mt-4 space-y-3">
            {models.map((model) => (
              <ModelCard
                key={model.model_id}
                model={model}
                onEdit={() => handleEdit(model)}
                onDelete={() => handleDelete(model.model_id)}
              />
            ))}
          </div>
        )}
      </Card>

      {toast && (
        <Toast message={toast.message} type={toast.type} onHidden={() => setToast(null)} />
      )}

      <ModelManager
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        model={editingModel}
        onSave={async () => {
          await loadModels();
          setModalOpen(false);
        }}
      />
    </div>
  );
}

function ModelCard({ model, onEdit, onDelete }: { model: LLMModel; onEdit: () => void; onDelete: () => void }) {
  const typeColors: Record<string, string> = {
    text: 'bg-blue-100 text-blue-800',
    image_audio: 'bg-green-100 text-green-800',
    general: 'bg-gray-100 text-gray-800',
  };

  return (
    <div className="flex items-center justify-between rounded-lg border border-primary-200 dark:border-primary-700 p-4 hover:border-primary-400">
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <h3 className="font-medium text-primary-900 dark:text-white">{model.name}</h3>
          <span className={`rounded-full px-2 py-0.5 text-xs ${typeColors[model.model_type] || typeColors.general}`}>
            {model.model_type.replace('_', ' ')}
          </span>
          {model.thinking_enabled && (
            <span className="rounded-full bg-purple-100 text-purple-800 px-2 py-0.5 text-xs">
              Thinking
            </span>
          )}
        </div>
        <p className="mt-1 text-xs text-primary-500 dark:text-primary-400">
          Model: <code>{model.model_name}</code>
        </p>
        <p className="text-xs text-primary-400 dark:text-primary-500">
          Endpoint: <code className="break-all">{model.endpoint}</code>
        </p>
        {model.vllm_version && (
          <p className="text-xs text-primary-400 dark:text-primary-500">
            vLLM: {model.vllm_version}
          </p>
        )}
      </div>
      <div className="flex gap-2">
        <Button variant="ghost" size="sm" onClick={onEdit}>Edit</Button>
        <Button variant="danger" size="sm" onClick={onDelete}>Delete</Button>
      </div>
    </div>
  );
}