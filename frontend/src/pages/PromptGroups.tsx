import { useState, useEffect, useCallback } from 'react';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import Textarea from '../components/ui/Textarea';
import Badge from '../components/ui/Badge';
import StatusBanner from '../components/ui/StatusBanner';
import Toast from '../components/ui/Toast';
import PromptSelector from '../components/ui/PromptSelector';
import { promptGroupsApi } from '../services/promptGroupsApi';
import type {
  PromptGroup,
  PromptGroupItemCreate,
  PromptGroupResult,
} from '../types/prompt';

const FONT_FAMILY =
  '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, "Fira Sans", "Droid Sans", "Helvetica Neue", sans-serif';

// ---------------------------------------------------------------------------
// Group Card (list view)
// ---------------------------------------------------------------------------
function GroupCard({
  group,
  onView,
  onExecute,
  onSchedule,
  onDelete,
  executing,
}: {
  group: PromptGroup;
  onView: () => void;
  onExecute: () => void;
  onSchedule: () => void;
  onDelete: () => void;
  executing: boolean;
}) {
  return (
    <div style={{ fontFamily: FONT_FAMILY }}>
    <Card className="flex flex-col gap-3">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="font-semibold text-primary-900 dark:text-white">{group.name}</h3>
          {group.description && (
            <p className="text-sm text-primary-500 dark:text-primary-400 mt-1">{group.description}</p>
          )}
        </div>
        <Badge variant="info">{group.items.length} prompts</Badge>
      </div>

      <div className="flex flex-wrap gap-1">
        {group.items.map((item) => (
          <Badge key={item.item_id} variant="neutral">
            #{item.position} {item.prompt_id}:v{item.prompt_version}
          </Badge>
        ))}
      </div>

      <div className="flex gap-2 mt-auto">
        <Button size="sm" onClick={onView}>
          View
        </Button>
        <Button size="sm" variant="primary" onClick={onExecute} disabled={executing}>
          {executing ? 'Running…' : 'Recalculate Now'}
        </Button>
        <Button size="sm" variant="secondary" onClick={onSchedule}>
          Schedule
        </Button>
        <Button size="sm" variant="danger" onClick={onDelete}>
          Delete
        </Button>
      </div>
    </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Create / Edit Modal
// ---------------------------------------------------------------------------
function GroupFormModal({
  initial,
  onSave,
  onCancel,
}: {
  initial?: PromptGroup | null;
  onSave: (data: { name: string; description: string | null; items: PromptGroupItemCreate[] }) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(initial?.name ?? '');
  const [description, setDescription] = useState(initial?.description ?? '');
  const [items, setItems] = useState<PromptGroupItemCreate[]>(
    initial?.items.map((i) => ({
      position: i.position,
      prompt_id: i.prompt_id,
      prompt_version: i.prompt_version,
    })) ?? [],
  );

  // PromptSelector value
  const [selectorValue, setSelectorValue] = useState<{ prompt_id: string; version?: number }>({
    prompt_id: '',
    version: undefined,
  });

  const handleSelectorChange = (val: { prompt_id: string; version?: number }) => {
    setSelectorValue(val);
  };

  const addPromptFromSelector = () => {
    if (!selectorValue.prompt_id || !selectorValue.version) return;
    setItems((prev) => [
      ...prev,
      {
        position: prev.length + 1,
        prompt_id: selectorValue.prompt_id,
        prompt_version: selectorValue.version!,
      },
    ]);
  };

  const removePrompt = (index: number) => {
    setItems((prev) => prev.filter((_, i) => i !== index).map((item, i) => ({ ...item, position: i + 1 })));
  };

  const movePrompt = (index: number, direction: 'up' | 'down') => {
    setItems((prev) => {
      const next = [...prev];
      const swapIdx = direction === 'up' ? index - 1 : index + 1;
      if (swapIdx < 0 || swapIdx >= next.length) return next;
      [next[index], next[swapIdx]] = [next[swapIdx], next[index]];
      return next.map((item, i) => ({ ...item, position: i + 1 }));
    });
  };

  const handleSave = () => {
    if (!name.trim()) return;
    onSave({ name: name.trim(), description: description.trim() || null, items });
  };

  const canAdd = selectorValue.prompt_id && selectorValue.version != null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div style={{ fontFamily: FONT_FAMILY }}>
      <Card className="w-full max-w-2xl max-h-[80vh] overflow-y-auto p-6">
        <h2 className="text-lg font-semibold mb-4 text-primary-900 dark:text-white">
          {initial ? 'Edit Group' : 'Create Group'}
        </h2>

        <div className="flex flex-col gap-4">
          <div>
            <label className="block text-sm font-medium text-primary-700 dark:text-primary-300 mb-1">
              Name
            </label>
            <input
              className="w-full rounded-md border border-surface-300 bg-white px-3 py-2 text-sm text-primary-800 placeholder:text-primary-400 focus:border-secondary-400 focus:outline-none focus:ring-2 focus:ring-secondary-400/20 dark:border-primary-600 dark:bg-primary-700 dark:text-white dark:placeholder:text-primary-500"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="My Prompt Chain"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-primary-700 dark:text-primary-300 mb-1">
              Description
            </label>
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional description…"
              rows={2}
            />
          </div>

          {/* Prompt Selector */}
          <div>
            <label className="block text-sm font-medium text-primary-700 dark:text-primary-300 mb-2">
              Select Prompt to Add
            </label>
            <PromptSelector value={selectorValue} onChange={handleSelectorChange} />
            <Button
              size="sm"
              variant="primary"
              onClick={addPromptFromSelector}
              disabled={!canAdd}
              className="mt-2"
            >
              + Add to Chain
            </Button>
          </div>

          {/* Chain Items */}
          <div>
            <label className="block text-sm font-medium text-primary-700 dark:text-primary-300 mb-2">
              Prompts in Chain
            </label>
            {items.length === 0 && (
              <p className="text-sm text-primary-500 dark:text-primary-400 mb-2">No prompts added yet.</p>
            )}
            {items.map((item, idx) => (
              <div key={idx} className="flex items-center gap-2 mb-2">
                <Badge variant="info">#{item.position}</Badge>
                <span className="text-sm flex-1 text-primary-800 dark:text-primary-200">
                  {item.prompt_id}:v{item.prompt_version}
                </span>
                <Button size="sm" onClick={() => movePrompt(idx, 'up')} disabled={idx === 0}>
                  ↑
                </Button>
                <Button size="sm" onClick={() => movePrompt(idx, 'down')} disabled={idx === items.length - 1}>
                  ↓
                </Button>
                <Button size="sm" variant="danger" onClick={() => removePrompt(idx)}>
                  ✕
                </Button>
              </div>
            ))}
          </div>

          <div className="flex gap-2 justify-end mt-4">
            <Button variant="secondary" onClick={onCancel}>
              Cancel
            </Button>
            <Button variant="primary" onClick={handleSave} disabled={!name.trim() || items.length === 0}>
              {initial ? 'Update' : 'Create'}
            </Button>
          </div>
        </div>
      </Card>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Detail View (modal)
// ---------------------------------------------------------------------------
function GroupDetailModal({
  group,
  onClose,
  onExecute,
  onEdit,
  onDelete,
}: {
  group: PromptGroup;
  onClose: () => void;
  onExecute: () => void;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const [results, setResults] = useState<PromptGroupResult[]>(group.results ?? []);
  const [executing, setExecuting] = useState(false);
  const [banner, setBanner] = useState<{ type: 'success' | 'error'; message: string } | null>(null);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  const loadResults = useCallback(async () => {
    try {
      const r = await promptGroupsApi.results(group.group_id);
      setResults(r);
    } catch {
      /* ignore */
    }
  }, [group.group_id]);

  useEffect(() => {
    loadResults();
  }, [loadResults]);

  const handleExecute = async () => {
    setExecuting(true);
    setBanner(null);
    try {
      await promptGroupsApi.execute(group.group_id);
      setBanner({ type: 'success', message: 'Chain executed successfully!' });
      setToast({ message: 'Chain executed!', type: 'success' });
      loadResults();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Execution failed';
      setBanner({ type: 'error', message: msg });
      setToast({ message: msg, type: 'error' });
    } finally {
      setExecuting(false);
    }
  };

  const handleSchedule = async () => {
    const input = prompt('Enter execution time (ISO 8601, e.g. 2026-07-01T10:00:00):');
    if (!input) return;
    try {
      await promptGroupsApi.schedule(group.group_id, { run_at: input });
      setToast({ message: 'Scheduled!', type: 'success' });
      onClose();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Scheduling failed';
      setToast({ message: msg, type: 'error' });
    }
  };

  const handleDelete = async () => {
    if (!confirm(`Delete "${group.name}"? This cannot be undone.`)) return;
    try {
      await promptGroupsApi.remove(group.group_id);
      setToast({ message: 'Group deleted', type: 'success' });
      onClose();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Delete failed';
      setToast({ message: msg, type: 'error' });
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      {toast && (
        <Toast message={toast.message} type={toast.type} onHidden={() => setToast(null)} />
      )}
      <div style={{ fontFamily: FONT_FAMILY }}>
      <Card className="w-full max-w-3xl max-h-[85vh] overflow-y-auto p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-primary-900 dark:text-white">{group.name}</h2>
          <Button size="sm" variant="secondary" onClick={onClose}>
            Close
          </Button>
        </div>

        {group.description && <p className="text-sm text-primary-500 dark:text-primary-400 mb-4">{group.description}</p>}

        {banner && (
          <StatusBanner type={banner.type} message={banner.message} />
        )}

        {/* Chain */}
        <div className="mb-4">
          <h3 className="font-medium mb-2 text-primary-900 dark:text-white">Chain ({group.items.length} prompts)</h3>
          {group.items.map((item, idx) => (
            <div key={item.item_id} className="flex items-center gap-2 mb-2">
              <Badge variant="info">#{item.position}</Badge>
              <span className="text-sm text-primary-800 dark:text-primary-200">
                {item.prompt_id}:v{item.prompt_version}
              </span>
              {idx < group.items.length - 1 && (
                <span className="text-primary-400">→</span>
              )}
            </div>
          ))}
        </div>

        {/* Actions */}
        <div className="flex gap-2 mb-4">
          <Button variant="primary" onClick={handleExecute} disabled={executing}>
            {executing ? 'Running…' : 'Recalculate Now'}
          </Button>
          <Button variant="secondary" onClick={handleSchedule}>
            Schedule
          </Button>
          <Button variant="secondary" onClick={onEdit}>
            Edit
          </Button>
          <Button variant="danger" onClick={handleDelete}>
            Delete
          </Button>
        </div>

        {/* Results History */}
        <div>
          <h3 className="font-medium mb-2 text-primary-900 dark:text-white">Execution History</h3>
          {results.length === 0 && <p className="text-sm text-primary-500 dark:text-primary-400">No executions yet.</p>}
          <div className="space-y-2">
            {results.map((r) => (
              <div key={r.result_id} className="flex items-center gap-3 text-sm border rounded p-2">
                <Badge variant={r.status === 'success' ? 'success' : r.status === 'failed' ? 'danger' : 'warning'}>
                  {r.status}
                </Badge>
                <span className="text-primary-800 dark:text-primary-200">{r.executed_at}</span>
                <Badge variant="neutral">{r.scheduled ? 'scheduled' : 'manual'}</Badge>
                {r.result_file && <span className="text-primary-400 truncate">{r.result_file}</span>}
                {r.error_message && (
                  <span className="text-red-500 truncate" title={r.error_message}>
                    {r.error_message}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      </Card>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------
export default function PromptGroups() {
  const [groups, setGroups] = useState<PromptGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingGroup, setEditingGroup] = useState<PromptGroup | null>(null);
  const [viewingGroup, setViewingGroup] = useState<PromptGroup | null>(null);
  const [executingId, setExecutingId] = useState<number | null>(null);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  const loadGroups = async () => {
    try {
      const data = await promptGroupsApi.list();
      setGroups(data);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Failed to load groups';
      setToast({ message: msg, type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadGroups();
  }, []);

  const handleCreate = async (data: { name: string; description: string | null; items: PromptGroupItemCreate[] }) => {
    try {
      await promptGroupsApi.create(data);
      setToast({ message: 'Group created!', type: 'success' });
      setShowForm(false);
      loadGroups();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Create failed';
      setToast({ message: msg, type: 'error' });
    }
  };

  const handleUpdate = async (data: { name: string; description: string | null; items: PromptGroupItemCreate[] }) => {
    if (!editingGroup) return;
    try {
      await promptGroupsApi.update(editingGroup.group_id, data);
      setToast({ message: 'Group updated!', type: 'success' });
      setEditingGroup(null);
      loadGroups();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Update failed';
      setToast({ message: msg, type: 'error' });
    }
  };

  const handleDelete = async (groupId: number) => {
    if (!confirm('Delete this group? This cannot be undone.')) return;
    try {
      await promptGroupsApi.remove(groupId);
      setToast({ message: 'Group deleted', type: 'success' });
      loadGroups();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Delete failed';
      setToast({ message: msg, type: 'error' });
    }
  };

  const handleExecute = async (groupId: number) => {
    setExecutingId(groupId);
    try {
      await promptGroupsApi.execute(groupId);
      setToast({ message: 'Chain executed!', type: 'success' });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Execution failed';
      setToast({ message: msg, type: 'error' });
    } finally {
      setExecutingId(null);
    }
  };

  if (loading) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-8" style={{ fontFamily: FONT_FAMILY }}>
        <PageHeader title="Prompt Groups" />
        <StatusBanner type="running" message="Loading…" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8" style={{ fontFamily: FONT_FAMILY }}>
      {toast && (
        <Toast message={toast.message} type={toast.type} onHidden={() => setToast(null)} />
      )}

      <div className="flex items-center justify-between mb-6">
        <PageHeader
          title="Prompt Groups"
          description="Create and manage prompt chains — sequences of prompts executed one after another."
        />
        <Button variant="primary" onClick={() => setShowForm(true)}>
          + New Group
        </Button>
      </div>

      {groups.length === 0 ? (
        <Card className="text-center py-12">
          <p className="text-primary-500 dark:text-primary-400 mb-4">No prompt groups yet. Create one to get started.</p>
          <Button variant="primary" onClick={() => setShowForm(true)}>
            + New Group
          </Button>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {groups.map((g) => (
            <GroupCard
              key={g.group_id}
              group={g}
              onView={() => setViewingGroup(g)}
              onExecute={() => handleExecute(g.group_id)}
              onSchedule={() => setViewingGroup(g)}
              onDelete={() => handleDelete(g.group_id)}
              executing={executingId === g.group_id}
            />
          ))}
        </div>
      )}

      {/* Modals */}
      {showForm && (
        <GroupFormModal
          onSave={handleCreate}
          onCancel={() => setShowForm(false)}
        />
      )}

      {editingGroup && (
        <GroupFormModal
          initial={editingGroup}
          onSave={handleUpdate}
          onCancel={() => setEditingGroup(null)}
        />
      )}

      {viewingGroup && (
        <GroupDetailModal
          group={viewingGroup}
          onClose={() => setViewingGroup(null)}
          onExecute={() => {
            handleExecute(viewingGroup.group_id);
          }}
          onEdit={() => {
            setViewingGroup(null);
            setEditingGroup(viewingGroup);
          }}
          onDelete={() => {
            handleDelete(viewingGroup.group_id);
            setViewingGroup(null);
          }}
        />
      )}
    </div>
  );
}