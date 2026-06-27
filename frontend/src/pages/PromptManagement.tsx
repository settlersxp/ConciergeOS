import { useState, useEffect } from "react";
import {
  PageHeader,
  Card,
  Button,
  Textarea,
  FormField,
  Select,
  Badge,
} from "../components/ui";
import {
  listAllPrompts,
  listVersions,
  create as createPrompt,
  update as updatePrompt,
  remove as deletePrompt,
  duplicate as duplicatePrompt,
  setDefault as setDefaultPrompt,
} from "../services/promptsApi";
import type { PromptVersion, PromptSummary, CreatePromptRequest, UpdatePromptRequest } from "../types/prompt";

export default function PromptManagement() {
  const [allPrompts, setAllPrompts] = useState<PromptSummary[]>([]);
  const [selectedPromptId, setSelectedPromptId] = useState<string>("");
  const [versions, setVersions] = useState<PromptVersion[]>([]);
  const [editingVersion, setEditingVersion] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<Omit<PromptVersion, "id" | "created_at" | "updated_at">>({
    prompt_id: "",
    version: 1,
    name: "",
    intention: "",
    restrictions: "",
    output_structure: "",
    user_prompt_template: "",
    is_default: false,
    metadata: null,
  });
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" | "info" } | null>(null);

  // Load all prompt IDs on mount
  useEffect(() => {
    listAllPrompts()
      .then((data) => {
        setAllPrompts(data);
        if (data.length > 0 && !selectedPromptId) {
          setSelectedPromptId(data[0].prompt_id);
        }
      })
      .catch(() => setToast({ message: "Failed to load prompts", type: "error" }));
  }, []);

  // Load versions when prompt ID changes
  useEffect(() => {
    if (!selectedPromptId) return;
    listVersions(selectedPromptId)
      .then(setVersions)
      .catch(() => setToast({ message: "Failed to load prompt versions", type: "error" }));
  }, [selectedPromptId]);

  const showNotification = (message: string, type: "success" | "error" | "info" = "info") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  };

  const handleSelectVersion = (version: number) => {
    const v = versions.find((p) => p.version === version);
    if (v) {
      setEditingVersion(version);
      setEditForm({
        prompt_id: v.prompt_id,
        version: v.version,
        name: v.name,
        intention: v.intention,
        restrictions: v.restrictions,
        output_structure: v.output_structure,
        user_prompt_template: v.user_prompt_template,
        is_default: v.is_default,
        metadata: v.metadata,
      });
    }
  };

  const handleCreateNew = () => {
    if (!selectedPromptId) {
      showNotification("Please select or create a prompt ID first", "error");
      return;
    }
    // Create v1 for a new prompt_id
    const newId = `new-prompt-${Date.now()}`;
    setSelectedPromptId(newId);
    setVersions([]);
    setEditingVersion(null);
    setEditForm({
      prompt_id: newId,
      version: 1,
      name: "New Prompt",
      intention: "",
      restrictions: "",
      output_structure: "",
      user_prompt_template: "{customer_name}",
      is_default: false,
      metadata: null,
    });
  };

  const handleSave = async () => {
    if (editingVersion !== null) {
      // Update existing
      setSaving(true);
      try {
        const updateData: UpdatePromptRequest = {
          name: editForm.name,
          intention: editForm.intention,
          restrictions: editForm.restrictions,
          output_structure: editForm.output_structure,
          user_prompt_template: editForm.user_prompt_template,
        };
        await updatePrompt(editForm.prompt_id, editingVersion, updateData);
        // Reload versions
        const updated = listVersions(editForm.prompt_id);
        setVersions(await updated);
        showNotification("Prompt updated successfully", "success");
      } catch (e: unknown) {
        showNotification(e instanceof Error ? e.message : "Save failed", "error");
      } finally {
        setSaving(false);
      }
    }
  };

  const handleSetDefault = async (version: number) => {
    try {
      await setDefaultPrompt(selectedPromptId, version);
      setVersions(await listVersions(selectedPromptId));
      showNotification(`Version ${version} set as default`, "success");
    } catch (e: unknown) {
      showNotification(e instanceof Error ? e.message : "Failed to set default", "error");
    }
  };

  const handleDuplicate = async () => {
    if (editingVersion === null) {
      showNotification("Select a version to duplicate", "error");
      return;
    }
    try {
      await duplicatePrompt(selectedPromptId, editingVersion);
      setVersions(await listVersions(selectedPromptId));
      showNotification("Prompt duplicated successfully", "success");
    } catch (e: unknown) {
      showNotification(e instanceof Error ? e.message : "Duplicate failed", "error");
    }
  };

  const handleDelete = async () => {
    if (editingVersion === null) return;
    if (!window.confirm(`Delete ${selectedPromptId}:v${editingVersion}?`)) return;
    try {
      await deletePrompt(selectedPromptId, editingVersion);
      setVersions(await listVersions(selectedPromptId));
      setEditingVersion(null);
      showNotification("Prompt deleted", "success");
    } catch (e: unknown) {
      showNotification(e instanceof Error ? e.message : "Delete failed", "error");
    }
  };

  const combinedSystemPrompt = [
    editForm.intention,
    editForm.restrictions,
    editForm.output_structure,
  ].filter(Boolean).join("\n\n");

  return (
    <div className="max-w-6xl mx-auto space-y-6 py-6 px-4">
      <PageHeader
        title="Prompt Management"
        description="Manage versioned prompts used across the application. Each prompt is composed of 4 structured fields that combine at runtime."
      />

      {toast && (
        <div
          className={`fixed top-4 right-4 z-50 px-4 py-3 rounded shadow-lg ${
            toast.type === "success"
              ? "bg-green-600 text-white"
              : toast.type === "error"
              ? "bg-red-600 text-white"
              : "bg-blue-600 text-white"
          }`}
        >
          {toast.message}
        </div>
      )}

      {/* Prompt ID Selector */}
      <Card title="Prompt ID">
        <div className="flex items-center gap-4">
          <FormField label="Select Prompt">
            <Select
              value={selectedPromptId}
              onChange={(e) => {
                setSelectedPromptId(e.target.value);
                setEditingVersion(null);
              }}
            >
              <option value="">Select a prompt...</option>
              {allPrompts.map((p) => (
                <option key={p.prompt_id} value={p.prompt_id}>
                  {p.prompt_id}
                </option>
              ))}
            </Select>
          </FormField>
          <Button variant="primary" onClick={handleCreateNew}>
            + Create New
          </Button>
        </div>
      </Card>

      {/* Versions Table */}
      {selectedPromptId && (
        <Card title={`Versions for ${selectedPromptId}`}>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-primary-200 dark:border-primary-700">
                  <th className="text-left py-2 px-3 font-medium">Name</th>
                  <th className="text-left py-2 px-3 font-medium">Version</th>
                  <th className="text-left py-2 px-3 font-medium">Default</th>
                  <th className="text-left py-2 px-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {versions.map((v) => (
                  <tr
                    key={v.id}
                    className={`border-b border-primary-100 dark:border-primary-800 cursor-pointer hover:bg-primary-50 dark:hover:bg-primary-900/30 ${
                      editingVersion === v.version ? "bg-primary-50 dark:bg-primary-900/50" : ""
                    }`}
                    onClick={() => handleSelectVersion(v.version)}
                  >
                    <td className="py-2 px-3">{v.name}</td>
                    <td className="py-2 px-3">
                      <Badge variant="info">v{v.version}</Badge>
                    </td>
                    <td className="py-2 px-3">
                      {v.is_default ? (
                        <Badge variant="success">★ Default</Badge>
                      ) : (
                        <Button
                          variant="ghost"
                          onClick={() => {
                            handleSetDefault(v.version);
                          }}
                        >
                          Set Default
                        </Button>
                      )}
                    </td>
                    <td className="py-2 px-3 space-x-1">
                      <Button
                        variant="ghost"
                        onClick={() => {
                          handleDuplicate();
                        }}
                      >
                        Duplicate
                      </Button>
                    </td>
                  </tr>
                ))}
                {versions.length === 0 && (
                  <tr>
                    <td colSpan={4} className="py-4 text-center text-primary-500">
                      No versions yet. Create a new prompt to get started.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Editor */}
      {editingVersion !== null && (
        <Card title={`Edit: ${selectedPromptId} v${editingVersion}`}>
          <div className="space-y-4">
            <FormField label="Display Name">
              <input
                type="text"
                className="w-full px-3 py-2 border border-primary-300 dark:border-primary-600 rounded bg-white dark:bg-primary-900 text-primary-900 dark:text-primary-100"
                value={editForm.name}
                onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
              />
            </FormField>

            <FormField label="Intention (System Prompt — Purpose)">
              <Textarea
                rows={6}
                className="w-full px-3 py-2 border border-primary-300 dark:border-primary-600 rounded bg-white dark:bg-primary-900 text-primary-900 dark:text-primary-100 resize-y"
                value={editForm.intention}
                onChange={(e) => setEditForm({ ...editForm, intention: e.target.value })}
              />
            </FormField>

            <FormField label="Restrictions (Rules & Constraints)">
              <Textarea
                rows={4}
                className="w-full px-3 py-2 border border-primary-300 dark:border-primary-600 rounded bg-white dark:bg-primary-900 text-primary-900 dark:text-primary-100 resize-y"
                value={editForm.restrictions}
                onChange={(e) => setEditForm({ ...editForm, restrictions: e.target.value })}
              />
            </FormField>

            <FormField label="Output Structure (Expected Response Format)">
              <Textarea
                rows={4}
                className="w-full px-3 py-2 border border-primary-300 dark:border-primary-600 rounded bg-white dark:bg-primary-900 text-primary-900 dark:text-primary-100 resize-y"
                value={editForm.output_structure}
                onChange={(e) => setEditForm({ ...editForm, output_structure: e.target.value })}
              />
            </FormField>

            <FormField label="User Prompt Template (Dynamic Message)">
              <Textarea
                rows={3}
                className="w-full px-3 py-2 border border-primary-300 dark:border-primary-600 rounded bg-white dark:bg-primary-900 text-primary-900 dark:text-primary-100 resize-y font-mono text-sm"
                value={editForm.user_prompt_template}
                onChange={(e) => setEditForm({ ...editForm, user_prompt_template: e.target.value })}
              />
            </FormField>

            {/* Preview */}
            <div>
              <h4 className="text-sm font-medium text-primary-700 dark:text-primary-300 mb-2">
                Preview (combined system prompt + resolved user message)
              </h4>
              <div className="p-3 bg-primary-50 dark:bg-primary-900/50 rounded border border-primary-200 dark:border-primary-700 font-mono text-xs space-y-2">
                <div>
                  <span className="font-bold text-primary-600 dark:text-primary-400">System: </span>
                  <pre className="whitespace-pre-wrap text-primary-800 dark:text-primary-200">
                    {combinedSystemPrompt || "(empty)"}
                  </pre>
                </div>
                <div>
                  <span className="font-bold text-primary-600 dark:text-primary-400">User: </span>
                  <pre className="whitespace-pre-wrap text-primary-800 dark:text-primary-200">
                    {editForm.user_prompt_template.replace("{customer_name}", "John Doe")}
                  </pre>
                </div>
              </div>
            </div>

            <div className="flex gap-2 pt-2">
              <Button variant="primary" onClick={handleSave} disabled={saving}>
                {saving ? "Saving..." : "Save Changes"}
              </Button>
              <Button
                variant="ghost"
                onClick={() => {
                  const v = versions.find((p) => p.version === editingVersion);
                  if (v) handleSelectVersion(v.version);
                  else setEditingVersion(null);
                }}
              >
                Cancel
              </Button>
              <Button
                variant="secondary"
                onClick={() => handleSetDefault(editingVersion)}
              >
                Set as Default
              </Button>
              <Button variant="danger" onClick={handleDelete}>
                Delete
              </Button>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}