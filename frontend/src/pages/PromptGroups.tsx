import { useState, useEffect, useCallback } from 'react';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import Textarea from '../components/ui/Textarea';
import Badge from '../components/ui/Badge';
import StatusBanner from '../components/ui/StatusBanner';
import Toast from '../components/ui/Toast';
import { promptGroupsApi } from '../services/promptGroupsApi';
import { listAllPrompts, listVersions } from '../services/promptsApi';
import type {
  PromptGroup,
  PromptGroupItemCreate,
  PromptGroupResult,
  PromptGroupSchedule,
} from '../types/prompt';
import type { PromptSummary, PromptVersion } from '../types/prompt';

const FONT_FAMILY =
  '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, "Fira Sans", "Droid Sans", "Helvetica Neue", sans-serif';

// ---------------------------------------------------------------------------
// Toggle Switch Component
// ---------------------------------------------------------------------------
function ToggleSwitch({ checked, onChange, disabled }: { checked: boolean; onChange: () => void; disabled?: boolean }) {
  return (
    <button
      type="button"
      onClick={onChange}
      disabled={disabled}
      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
        checked ? 'bg-secondary-500' : 'bg-primary-300 dark:bg-primary-600'
      } ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
    >
      <span
        className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
          checked ? 'translate-x-6' : 'translate-x-1'
        }`}
      />
    </button>
  );
}

// ---------------------------------------------------------------------------
// Group Card (list view)
// ---------------------------------------------------------------------------
function GroupCard({
  group,
  onView,
  onExecute,
  onToggle,
  onDelete,
  onToggleItem,
  executing,
}: {
  group: PromptGroup;
  onView: () => void;
  onExecute: () => void;
  onToggle: () => void;
  onDelete: () => void;
  onToggleItem: (itemId: number) => void;
  executing: boolean;
}) {
  const activeSchedules = group.schedules?.filter((s) => s.active) ?? [];

  return (
    <div style={{ fontFamily: FONT_FAMILY }}>
      <Card className={`flex flex-col gap-3 transition-opacity ${!group.is_active ? 'opacity-50' : ''}`}>
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-semibold text-primary-900 dark:text-white">{group.name}</h3>
              {!group.is_active && <Badge variant="danger">Disabled</Badge>}
            </div>
            {group.description && (
              <p className="text-sm text-primary-500 dark:text-primary-400 mt-1">{group.description}</p>
            )}
          </div>
          <div className="flex items-center gap-2">
            <ToggleSwitch checked={group.is_active} onChange={onToggle} />
            <Badge variant="info">{group.items.length}</Badge>
          </div>
        </div>

        <div className="flex flex-wrap gap-1">
          {group.items.map((item) => (
            <div key={item.item_id} className="flex items-center gap-1">
              <Badge variant={item.is_active ? "neutral" : "danger"}>
                #{item.position} {item.prompt_id}:v{item.prompt_version}
              </Badge>
              <ToggleSwitch
                checked={item.is_active ?? true}
                onChange={() => onToggleItem(item.item_id)}
              />
            </div>
          ))}
        </div>

        {activeSchedules.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {activeSchedules.map((s) => (
              <Badge key={s.schedule_id} variant="warning">
                ⏰ {new Date(s.run_at).toLocaleString()}
              </Badge>
            ))}
          </div>
        )}

        <div className="flex gap-2 mt-auto">
          <Button size="sm" onClick={onView}>
            View
          </Button>
          <Button size="sm" variant="primary" onClick={onExecute} disabled={executing || !group.is_active}>
            {executing ? 'Running…' : 'Recalculate Now'}
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
// Schedule Management Modal
// ---------------------------------------------------------------------------
function ScheduleModal({
  group,
  onClose,
}: {
  group: PromptGroup;
  onClose: () => void;
}) {
  const [scheduleType, setScheduleType] = useState<'daily' | 'weekly' | 'none'>('daily');
  const [runAt, setRunAt] = useState('');
  const [timeOnly, setTimeOnly] = useState('15:00');
  const [schedules, setSchedules] = useState<PromptGroupSchedule[]>(group.schedules ?? []);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  const refresh = useCallback(async () => {
    try {
      const g = await promptGroupsApi.get(group.group_id);
      setSchedules(g.schedules ?? []);
    } catch {
      /* ignore */
    }
  }, [group.group_id]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleSchedule = async () => {
    // For "none", require full datetime; for daily/weekly, build datetime from today + time
    let runAtIso: string;
    if (scheduleType === 'none') {
      if (!runAt) return;
      runAtIso = runAt;
    } else {
      if (!timeOnly) return;
      const [hours, minutes] = timeOnly.split(':');
      const now = new Date();
      now.setHours(parseInt(hours, 10), parseInt(minutes, 10), 0, 0);
      runAtIso = now.toISOString();
    }
    try {
      await promptGroupsApi.schedule(group.group_id, { run_at: runAtIso, schedule_type: scheduleType });
      setToast({ message: 'Scheduled!', type: 'success' });
      if (scheduleType === 'none') {
        setRunAt('');
      }
      refresh();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Scheduling failed';
      setToast({ message: msg, type: 'error' });
    }
  };

  const handleCancel = async (scheduleId: number) => {
    try {
      await promptGroupsApi.cancelSchedule(group.group_id, scheduleId);
      setToast({ message: 'Schedule cancelled', type: 'success' });
      refresh();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Cancel failed';
      setToast({ message: msg, type: 'error' });
    }
  };

  const activeSchedules = schedules.filter((s) => s.active);
  const inactiveSchedules = schedules.filter((s) => !s.active);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      {toast && <Toast message={toast.message} type={toast.type} onHidden={() => setToast(null)} />}
      <div style={{ fontFamily: FONT_FAMILY }}>
        <Card className="w-full max-w-lg max-h-[80vh] overflow-y-auto p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-primary-900 dark:text-white">
              Schedules for {group.name}
            </h2>
            <Button size="sm" variant="secondary" onClick={onClose}>
              Close
            </Button>
          </div>

          {/* Add new schedule */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-primary-700 dark:text-primary-300 mb-1">
              Schedule New Execution
            </label>
            <div className="flex flex-col gap-2">
              {/* Schedule type dropdown */}
              <select
                className="rounded-md border border-surface-300 bg-white px-3 py-2 text-sm text-primary-800 focus:border-secondary-400 focus:outline-none focus:ring-2 focus:ring-secondary-400/20 dark:border-primary-600 dark:bg-primary-700 dark:text-white"
                value={scheduleType}
                onChange={(e) => setScheduleType(e.target.value as 'daily' | 'weekly' | 'none')}
              >
                <option value="daily">Daily</option>
                <option value="weekly">Weekly</option>
                <option value="none">None (one-time)</option>
              </select>
              {/* Time input for recurring, datetime for one-time */}
              {scheduleType === 'none' ? (
                <input
                  type="datetime-local"
                  className="rounded-md border border-surface-300 bg-white px-3 py-2 text-sm text-primary-800 focus:border-secondary-400 focus:outline-none focus:ring-2 focus:ring-secondary-400/20 dark:border-primary-600 dark:bg-primary-700 dark:text-white"
                  value={runAt}
                  onChange={(e) => setRunAt(e.target.value)}
                />
              ) : (
                <input
                  type="time"
                  className="rounded-md border border-surface-300 bg-white px-3 py-2 text-sm text-primary-800 focus:border-secondary-400 focus:outline-none focus:ring-2 focus:ring-secondary-400/20 dark:border-primary-600 dark:bg-primary-700 dark:text-white"
                  value={timeOnly}
                  onChange={(e) => setTimeOnly(e.target.value)}
                />
              )}
              <div className="flex justify-end">
                <Button
                  size="sm"
                  variant="primary"
                  onClick={handleSchedule}
                  disabled={scheduleType === 'none' ? !runAt : !timeOnly}
                >
                  + Schedule
                </Button>
              </div>
            </div>
          </div>

          {/* Active schedules */}
          <div className="mb-4">
            <h3 className="text-sm font-medium text-primary-700 dark:text-primary-300 mb-2">
              Active ({activeSchedules.length})
            </h3>
            {activeSchedules.length === 0 && (
              <p className="text-sm text-primary-500 dark:text-primary-400">No active schedules.</p>
            )}
            {activeSchedules.map((s) => (
              <div key={s.schedule_id} className="flex items-center justify-between gap-2 text-sm border rounded p-2 mb-2">
                <div className="flex-1">
                  <span className="text-primary-800 dark:text-primary-200">
                    {new Date(s.run_at).toLocaleString()}
                  </span>
                  <Badge variant="warning" className="ml-2">pending</Badge>
                </div>
                <Button size="sm" variant="danger" onClick={() => handleCancel(s.schedule_id)}>
                  Cancel
                </Button>
              </div>
            ))}
          </div>

          {/* Past/Cancelled schedules */}
          {inactiveSchedules.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-primary-700 dark:text-primary-300 mb-2">
                Past / Cancelled ({inactiveSchedules.length})
              </h3>
              {inactiveSchedules.map((s) => (
                <div key={s.schedule_id} className="flex items-center gap-2 text-sm text-primary-500 dark:text-primary-400 border rounded p-2 mb-2">
                  <span>{new Date(s.run_at).toLocaleString()}</span>
                  <Badge variant="neutral">cancelled</Badge>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
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
  onSave: (data: { name: string; description: string | null; items: PromptGroupItemCreate[]; is_chain_page?: boolean; page_route?: string | null }) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(initial?.name ?? '');
  const [description, setDescription] = useState(initial?.description ?? '');
  const [isChainPage, setIsChainPage] = useState(initial?.is_chain_page ?? false);
  const [pageRoute, setPageRoute] = useState(initial?.page_route ?? '');
  const [items, setItems] = useState<PromptGroupItemCreate[]>(
    initial?.items.map((i) => ({
      position: i.position,
      prompt_id: i.prompt_id,
      prompt_version: i.prompt_version,
      alias: i.alias,
      is_input_step: i.is_input_step,
    })) ?? [],
  );

  // Simple prompt/version selectors (no model selector)
  const [allPrompts, setAllPrompts] = useState<PromptSummary[]>([]);
  const [addPromptId, setAddPromptId] = useState('');
  const [addVersions, setAddVersions] = useState<PromptVersion[]>([]);
  const [addVersion, setAddVersion] = useState<number | undefined>(undefined);

  // Load all prompts on mount
  useEffect(() => {
    listAllPrompts()
      .then((data) => {
        setAllPrompts(data);
        if (data.length > 0 && !addPromptId) {
          setAddPromptId(data[0].prompt_id);
        }
      })
      .catch(() => {});
  }, []);

  // Load versions when prompt changes
  useEffect(() => {
    if (addPromptId) {
      listVersions(addPromptId)
        .then((data) => {
          setAddVersions(data);
          const highest = [...data].sort((a, b) => b.version - a.version)[0];
          setAddVersion(highest?.version);
        })
        .catch(() => setAddVersions([]));
    } else {
      setAddVersions([]);
      setAddVersion(undefined);
    }
  }, [addPromptId]);

  const addPromptFromSelector = () => {
    if (!addPromptId || addVersion === undefined) return;
    setItems((prev) => [
      ...prev,
      {
        position: prev.length + 1,
        prompt_id: addPromptId,
        prompt_version: addVersion,
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

  const toggleInputStep = (index: number) => {
    setItems((prev) => prev.map((item, i) => (i === index ? { ...item, is_input_step: !item.is_input_step } : item)));
  };

  const handleSave = () => {
    if (!name.trim()) return;
    const route = isChainPage ? (pageRoute.replace(/^\//, '') || null) : null;
    onSave({ name: name.trim(), description: description.trim() || null, items, is_chain_page: isChainPage, page_route: route });
  };

  const canAdd = addPromptId && addVersion != null;

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

           {/* Is Chain Page toggle */}
           <div className="flex items-center gap-3">
             <ToggleSwitch
               checked={isChainPage}
               onChange={() => setIsChainPage(!isChainPage)}
             />
             <div>
               <label className="text-sm font-medium text-primary-700 dark:text-primary-300">
                 Is Chain Page
               </label>
               <p className="text-xs text-primary-500 dark:text-primary-400">
                 Enable to create a page accessible at /prompt-chains/{'...'}
               </p>
             </div>
           </div>

           {/* Page Route (only shown when Is Chain Page is enabled) */}
           {isChainPage && (
             <div>
               <label className="block text-sm font-medium text-primary-700 dark:text-primary-300 mb-1">
                 Page Route
               </label>
               <input
                 className="w-full rounded-md border border-surface-300 bg-white px-3 py-2 text-sm text-primary-800 placeholder:text-primary-400 focus:border-secondary-400 focus:outline-none focus:ring-2 focus:ring-secondary-400/20 dark:border-primary-600 dark:bg-primary-700 dark:text-white dark:placeholder:text-primary-500"
                 value={pageRoute}
                 onChange={(e) => setPageRoute(e.target.value)}
                 placeholder={`e.g., ${name.toLowerCase().replace(/\s+/g, '-') || 'my-page'}`}
                 disabled={!isChainPage}
               />
                {pageRoute && (
                  <p className="mt-1 text-xs text-secondary-500">
                    URL: <code>/prompt-chains/{pageRoute.replace(/^\//, '')}</code>
                  </p>
                )}
             </div>
           )}

          {/* Simple Prompt/Version Selectors */}
          <div>
            <label className="block text-sm font-medium text-primary-700 dark:text-primary-300 mb-2">
              Select Prompt to Add
            </label>
            <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
              <select
                className="rounded-md border border-surface-300 bg-white px-3 py-2 text-sm text-primary-800 focus:border-secondary-400 focus:outline-none focus:ring-2 focus:ring-secondary-400/20 dark:border-primary-600 dark:bg-primary-700 dark:text-white"
                value={addPromptId}
                onChange={(e) => setAddPromptId(e.target.value)}
              >
                <option value="">-- Select Prompt --</option>
                {allPrompts.map((p) => (
                  <option key={p.prompt_id} value={p.prompt_id}>
                    {p.prompt_id} ({p.version_count} version{p.version_count !== 1 ? 's' : ''})
                  </option>
                ))}
              </select>
              <select
                className="rounded-md border border-surface-300 bg-white px-3 py-2 text-sm text-primary-800 focus:border-secondary-400 focus:outline-none focus:ring-2 focus:ring-secondary-400/20 dark:border-primary-600 dark:bg-primary-700 dark:text-white"
                value={addVersion ?? ''}
                onChange={(e) => setAddVersion(e.target.value ? Number(e.target.value) : undefined)}
                disabled={!addPromptId || addVersions.length === 0}
              >
                <option value="">
                  {!addPromptId ? 'Select a prompt first' : addVersions.length === 0 ? 'No versions' : 'Select version'}
                </option>
                {addVersions.map((v) => (
                  <option key={v.version} value={v.version}>
                    v{v.version}{v.is_default ? ' (default)' : ''}
                  </option>
                ))}
              </select>
            </div>
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
                 <button
                   type="button"
                   onClick={() => toggleInputStep(idx)}
                   className={`text-xs px-2 py-1 rounded border transition-colors ${
                     item.is_input_step
                       ? 'bg-secondary-100 border-secondary-400 text-secondary-700 dark:bg-secondary-900 dark:border-secondary-600 dark:text-secondary-300'
                       : 'bg-white border-surface-300 text-primary-500 hover:border-secondary-400 dark:bg-primary-700 dark:border-primary-600 dark:text-primary-400'
                   }`}
                   title="Mark as input step (user provides input on chain page)"
                 >
                   Input Step
                 </button>
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
  onEdit,
  onToggle,
  onToggleItem,
  onOpenSchedules,
}: {
  group: PromptGroup;
  onClose: () => void;
  onEdit: () => void;
  onToggle: () => void;
  onToggleItem: (itemId: number) => void;
  onOpenSchedules: () => void;
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

  const activeSchedules = group.schedules?.filter((s) => s.active) ?? [];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      {toast && (
        <Toast message={toast.message} type={toast.type} onHidden={() => setToast(null)} />
      )}
      <div style={{ fontFamily: FONT_FAMILY }}>
      <Card className="w-full max-w-3xl max-h-[85vh] overflow-y-auto p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold text-primary-900 dark:text-white">{group.name}</h2>
            {!group.is_active && <Badge variant="danger">Disabled</Badge>}
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm text-primary-500 dark:text-primary-400">
              {group.is_active ? 'Active' : 'Disabled'}
            </span>
            <ToggleSwitch checked={group.is_active} onChange={onToggle} />
            <Button size="sm" variant="secondary" onClick={onClose}>
              Close
            </Button>
          </div>
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
              <Badge variant={item.is_active ? "info" : "neutral"}>#{item.position}</Badge>
              <span className={`text-sm ${item.is_active ? 'text-primary-800 dark:text-primary-200' : 'text-primary-400 dark:text-primary-500 line-through'}`}>
                {item.prompt_id}:v{item.prompt_version}
              </span>
              <ToggleSwitch
                checked={item.is_active ?? true}
                onChange={() => onToggleItem(item.item_id)}
              />
              {idx < group.items.length - 1 && (
                <span className="text-primary-400">→</span>
              )}
            </div>
          ))}
        </div>

        {/* Active Schedules */}
        {activeSchedules.length > 0 && (
          <div className="mb-4">
            <h3 className="font-medium mb-2 text-primary-900 dark:text-white">
              Active Schedules ({activeSchedules.length})
            </h3>
            {activeSchedules.map((s) => (
              <div key={s.schedule_id} className="flex items-center gap-2 text-sm border rounded p-2 mb-2">
                <Badge variant="warning">⏰</Badge>
                <span className="text-primary-800 dark:text-primary-200">
                  {new Date(s.run_at).toLocaleString()}
                </span>
              </div>
            ))}
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-2 mb-4">
          <Button variant="primary" onClick={handleExecute} disabled={executing || !group.is_active}>
            {executing ? 'Running…' : 'Recalculate Now'}
          </Button>
          <Button variant="secondary" onClick={onOpenSchedules}>
            Manage Schedules
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
                {r.status === 'success' && r.result_file && (
                  <div className="flex gap-1 ml-auto">
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => window.open(`/api/prompt-groups/results/${r.result_id}/download`, '_blank')}
                    >
                      View
                    </Button>
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => {
                        const link = document.createElement('a');
                        link.href = `/api/prompt-groups/results/${r.result_id}/download`;
                        link.download = '';
                        document.body.appendChild(link);
                        link.click();
                        document.body.removeChild(link);
                      }}
                    >
                      Download
                    </Button>
                  </div>
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
  const [scheduleGroup, setScheduleGroup] = useState<PromptGroup | null>(null);
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

  const handleToggle = async (groupId: number) => {
    try {
      await promptGroupsApi.toggle(groupId);
      loadGroups();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Toggle failed';
      setToast({ message: msg, type: 'error' });
    }
  };

  const handleToggleItem = async (groupId: number, itemId: number) => {
    try {
      await promptGroupsApi.toggleItem(groupId, itemId);
      if (viewingGroup?.group_id === groupId) {
        setViewingGroup({
          ...viewingGroup,
          items: viewingGroup.items.map((item) =>
            item.item_id === itemId ? { ...item, is_active: !item.is_active } : item
          ),
        });
      }
      loadGroups();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Toggle failed';
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
              onToggle={() => handleToggle(g.group_id)}
              onDelete={() => handleDelete(g.group_id)}
              onToggleItem={(itemId) => handleToggleItem(g.group_id, itemId)}
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
          onEdit={() => {
            setViewingGroup(null);
            setEditingGroup(viewingGroup);
          }}
          onToggle={() => handleToggle(viewingGroup.group_id)}
          onToggleItem={(itemId) => handleToggleItem(viewingGroup.group_id, itemId)}
          onOpenSchedules={() => {
            setScheduleGroup(viewingGroup);
          }}
        />
      )}

      {scheduleGroup && (
        <ScheduleModal
          group={scheduleGroup}
          onClose={() => {
            setScheduleGroup(null);
            loadGroups();
          }}
        />
      )}
    </div>
  );
}