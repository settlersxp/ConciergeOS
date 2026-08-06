import { useState, useEffect } from 'react';
import { listAllPrompts, getByVersion, listVersions } from '../../services/promptsApi';
import type { PromptSummary, PromptVersion } from '../../types/prompt';
import { Button, Select, Card } from './';

interface CloneSectionModalProps {
  open: boolean;
  section: string;
  sectionLabel: string;
  currentPromptId: string;
  currentVersion: number;
  onClose: () => void;
  onClone: (text: string) => void;
}

export default function CloneSectionModal({
  open,
  section,
  sectionLabel,
  currentPromptId,
  currentVersion,
  onClose,
  onClone,
}: CloneSectionModalProps) {
  const [allPrompts, setAllPrompts] = useState<PromptSummary[]>([]);
  const [sourcePromptId, setSourcePromptId] = useState('');
  const [sourceVersions, setSourceVersions] = useState<PromptVersion[]>([]);
  const [sourceVersion, setSourceVersion] = useState<number | null>(null);
  const [previewText, setPreviewText] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [versionsLoading, setVersionsLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (open) {
      resetState();
      loadPrompts();
    }
  }, [open]);

  useEffect(() => {
    if (sourcePromptId) {
      loadVersions(sourcePromptId);
    } else {
      setSourceVersions([]);
      setSourceVersion(null);
      setPreviewText(null);
    }
  }, [sourcePromptId]);

  useEffect(() => {
    if (sourcePromptId && sourceVersion !== null) {
      loadPreview();
    } else {
      setPreviewText(null);
    }
  }, [sourcePromptId, sourceVersion]);

  function resetState() {
    setAllPrompts([]);
    setSourcePromptId('');
    setSourceVersions([]);
    setSourceVersion(null);
    setPreviewText(null);
    setError('');
    setLoading(false);
    setVersionsLoading(false);
  }

  async function loadPrompts() {
    setLoading(true);
    setError('');
    try {
      const prompts = await listAllPrompts();
      setAllPrompts(prompts);
    } catch (e) {
      setError('Failed to load prompts');
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  async function loadVersions(promptId: string) {
    setVersionsLoading(true);
    setError('');
    try {
      const versions = await listVersions(promptId);
      setSourceVersions(versions);
      if (versions.length > 0) {
        setSourceVersion(versions[0].version);
      } else {
        setSourceVersion(null);
      }
    } catch (e) {
      setError('Failed to load versions');
      console.error(e);
    } finally {
      setVersionsLoading(false);
    }
  }

  async function loadPreview() {
    if (sourceVersion === null) return;
    setLoading(true);
    setError('');
    try {
      const version = await getByVersion(sourcePromptId, sourceVersion);
      const text = (version as any)[section] ?? '';
      setPreviewText(text);
    } catch (e) {
      setError('Failed to load section preview');
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  function handleClone() {
    onClone(previewText ?? '');
    onClose();
  }

  const handleClose = () => {
    if (!loading) {
      onClose();
    }
  };

  if (!open) return null;

  const filteredPrompts = allPrompts.filter(
    (p) => !(p.prompt_id === currentPromptId && p.default_version === currentVersion)
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <Card title={`Clone ${sectionLabel}`} className="w-full max-w-md">
        {/* Close button overlay */}
        <button
          onClick={handleClose}
          className="absolute top-4 right-4 text-primary-500 hover:text-primary-700 dark:text-primary-400 dark:hover:text-white text-2xl leading-none"
        >
          &times;
        </button>

        <div className="space-y-4">
          {error && (
            <div className="rounded-md bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 px-3 py-2 text-sm text-red-700 dark:text-red-400">
              {error}
            </div>
          )}

          {/* Source Prompt Selector */}
          <div>
            <label className="block text-sm font-medium text-primary-700 dark:text-primary-300 mb-1">
              Source Prompt
            </label>
            <Select
              value={sourcePromptId}
              onChange={(e) => {
                setSourcePromptId(e.target.value);
                setSourceVersion(null);
                setPreviewText(null);
              }}
              disabled={loading}
            >
              <option value="">— Select prompt —</option>
              {filteredPrompts.map((p) => (
                <option key={p.prompt_id} value={p.prompt_id}>
                  {p.prompt_id} (v{p.default_version})
                </option>
              ))}
            </Select>
            {loading && !sourcePromptId && (
              <p className="mt-1 text-xs text-primary-500 dark:text-primary-400">Loading prompts...</p>
            )}
          </div>

          {/* Source Version Selector */}
          {sourcePromptId && (
            <div>
              <label className="block text-sm font-medium text-primary-700 dark:text-primary-300 mb-1">
                Source Version
              </label>
              <Select
                value={sourceVersion ?? ''}
                onChange={(e) => setSourceVersion(Number(e.target.value))}
                disabled={versionsLoading}
              >
                {sourceVersions.map((v) => (
                  <option key={v.version} value={v.version}>
                    Version {v.version}{v.is_default ? ' (default)' : ''}
                  </option>
                ))}
              </Select>
              {versionsLoading && (
                <p className="mt-1 text-xs text-primary-500 dark:text-primary-400">Loading versions...</p>
              )}
            </div>
          )}

          {/* Preview */}
          {sourceVersion !== null && previewText !== null && (
            <div>
              <label className="block text-sm font-medium text-primary-700 dark:text-primary-300 mb-1">
                Section Preview
              </label>
              <pre className="whitespace-pre-wrap text-sm p-3 rounded-md border border-surface-200 dark:border-primary-700 bg-white dark:bg-primary-900 max-h-48 overflow-y-auto text-primary-800 dark:text-primary-200">
                {previewText || <span className="text-primary-400 dark:text-primary-500 italic">(empty section)</span>}
              </pre>
              <p className="mt-1 text-xs text-primary-500 dark:text-primary-400">
                From {sourcePromptId} v{sourceVersion}
              </p>
            </div>
          )}

          {loading && sourcePromptId && sourceVersion !== null && (
            <p className="text-xs text-primary-500 dark:text-primary-400">Loading preview...</p>
          )}
        </div>

        <div className="flex justify-end gap-2 mt-6">
          <Button onClick={handleClose} disabled={loading} variant="ghost">
            Cancel
          </Button>
          <Button
            onClick={handleClone}
            disabled={!sourceVersion || loading || previewText === null}
            variant="primary"
          >
            Clone
          </Button>
        </div>
      </Card>
    </div>
  );
}