import { useState, useRef, useEffect } from 'react';
import { Button, Input, Card } from './';
import { promptsApi } from '../../services/promptsApi';

interface CreatePromptModalProps {
  open: boolean;
  onClose: () => void;
  onCreate: (promptId: string) => void;
}

const KEBAB_CASE_REGEX = /^[a-z][a-z0-9-]*$/;

export default function CreatePromptModal({ open, onClose, onCreate }: CreatePromptModalProps) {
  const [promptId, setPromptId] = useState('');
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const [creating, setCreating] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setPromptId('');
      setName('');
      setError('');
      setCreating(false);
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [open]);

  const validatePromptId = (value: string) => {
    if (!value) return 'Prompt ID is required';
    if (!KEBAB_CASE_REGEX.test(value)) {
      return 'Must be kebab-case: start with lowercase letter, use only lowercase letters, numbers, and hyphens (e.g., "guest-search")';
    }
    return '';
  };

  const handlePromptIdChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setPromptId(value);
    setError(validatePromptId(value));
  };

  const handleCreate = async () => {
    const validationError = validatePromptId(promptId);
    if (validationError) {
      setError(validationError);
      return;
    }
    if (!name.trim()) {
      setError('Name is required');
      return;
    }

    setCreating(true);
    setError('');

    try {
      await promptsApi.create(promptId, {
        name: name.trim(),
        intention: '',
        restrictions: '',
        output_structure: '',
        user_prompt_template: '',
      });
      onCreate(promptId);
      onClose();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create prompt';
      setError(message);
    } finally {
      setCreating(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !creating) {
      e.preventDefault();
      handleCreate();
    }
  };

  const handleClose = () => {
    if (!creating) {
      onClose();
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <Card title="Create New Prompt" className="w-full max-w-md">
        {/* Close button overlay */}
        <button
          onClick={handleClose}
          className="absolute top-4 right-4 text-primary-500 hover:text-primary-700 dark:text-primary-400 dark:hover:text-white text-2xl leading-none"
        >
          &times;
        </button>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-primary-700 dark:text-primary-300 mb-1">
              Prompt ID
            </label>
            <Input
              ref={inputRef}
              type="text"
              value={promptId}
              onChange={handlePromptIdChange}
              onKeyDown={handleKeyDown}
              placeholder="e.g., guest-search"
              disabled={creating}
              helperText={'Must be kebab-case (e.g., "my-new-prompt")'}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-primary-700 dark:text-primary-300 mb-1">
              Display Name
            </label>
            <Input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="e.g., Guest Search Prompt"
              disabled={creating}
            />
          </div>

          {error && (
            <div className="rounded-md bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 px-3 py-2 text-sm text-red-700 dark:text-red-400">
              {error}
            </div>
          )}
        </div>

        <div className="flex justify-end gap-2 mt-6">
          <Button onClick={handleClose} disabled={creating} variant="ghost">
            Cancel
          </Button>
          <Button onClick={handleCreate} disabled={creating || !!error || !name.trim()} variant="primary" loading={creating}>
            Create
          </Button>
        </div>
      </Card>
    </div>
  );
}