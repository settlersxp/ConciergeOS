import { useState, useEffect, useRef } from "react";
import {
  PageHeader, Card, Button, Toast,
  PlaceholderPalette, PreviewPanel, PromptEditorSection,
  PromptSelector, CreatePromptModal, PromptImprovementChat, CloneSectionModal,
} from "../components/ui";
import {
  listVersions, create as createPrompt,
  update as updatePrompt, remove as deletePrompt,
  setDefault as setDefaultPrompt,
  listPlaceholders, previewPrompt,
  listAllPrompts, duplicate,
} from "../services/promptsApi";
import type { PromptVersion, PromptSummary } from "../types/prompt";
import type { PlaceholderDefinition } from "../types/placeholder";

export default function PromptManagement() {
  const [, setAllPrompts] = useState<PromptSummary[]>([]);
  const [selectedPromptId, setSelectedPromptId] = useState("");
  const [versions, setVersions] = useState<PromptVersion[]>([]);
  const [editingVersion, setEditingVersion] = useState<number | null>(null);
  const [editForm, setEditForm] = useState({
    prompt_id: "", version: 1, name: "", intention: "", restrictions: "", output_structure: "", user_prompt_template: "", is_default: false, metadata: undefined as Record<string, unknown> | undefined,
  });
  const [saving, setSaving] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [toastType, setToastType] = useState<"success" | "error" | "info">("info");
  const [placeholders, setPlaceholders] = useState<PlaceholderDefinition[]>([]);
  const [showPreview, setShowPreview] = useState(false);
  const [resolvedPreview, setResolvedPreview] = useState<{ system: string; user: string } | null>(null);
  const [runtimeVariables, setRuntimeVariables] = useState<Record<string, string>>({});
  const [_loading, setLoading] = useState(false);
  const selectorRefetchRef = useRef<(() => void) | undefined>(undefined);

  // Create Prompt Modal state
  const [showCreateModal, setShowCreateModal] = useState(false);

  // AI Improvement Chat state
  const [showImprovementChat, setShowImprovementChat] = useState(false);
  const [improvingSection, setImprovingSection] = useState<string>("");

  // Clone Section Modal state
  const [showCloneModal, setShowCloneModal] = useState(false);
  const [cloningSection, setCloningSection] = useState<string>("");

  // Load all prompts on mount
  useEffect(() => {
    listAllPrompts()
      .then((data) => {
        setAllPrompts(data);
        if (data.length > 0 && !selectedPromptId) {
          setSelectedPromptId(data[0].prompt_id);
        }
      })
      .catch(() => showNotification("Failed to load prompts", "error"));
  }, []);

  const showNotification = (message: string, type: "success" | "error" | "info" = "info") => {
    setToastMessage(message);
    setToastType(type);
    setTimeout(() => setToastMessage(null), 3000);
  };

  const hideToast = () => setToastMessage(null);

  // Load placeholders on mount
  useEffect(() => {
    listPlaceholders()
      .then((data) => {
        const placeholders = (data as { placeholders?: PlaceholderDefinition[] }).placeholders;
        if (placeholders) {
          setPlaceholders(placeholders);
        }
      })
      .catch(() => {});
  }, []);

  // Load versions when a prompt is selected
  useEffect(() => {
    if (!selectedPromptId) {
      setVersions([]);
      setEditingVersion(null);
      setEditForm({
        prompt_id: "", version: 1, name: "", intention: "", restrictions: "", output_structure: "", user_prompt_template: "", is_default: false, metadata: undefined,
      });
      return;
    }
    setLoading(true);
    listVersions(selectedPromptId)
      .then((data) => {
        setVersions(data);
        // Auto-select the default version or the first version
        const def = data.find((v: PromptVersion) => v.is_default);
        const selected = def || (data.length > 0 ? data[0] : null);

        if (selected) {
          setEditingVersion(selected.version);
          setEditForm({
            prompt_id: selected.prompt_id,
            version: selected.version,
            name: selected.name || "",
            intention: selected.intention || "",
            restrictions: selected.restrictions || "",
            output_structure: selected.output_structure || "",
            user_prompt_template: selected.user_prompt_template || "",
            is_default: selected.is_default || false,
            metadata: selected.metadata || undefined,
          });
        } else {
          setEditingVersion(null);
        }
      })
      .catch(() => showNotification("Failed to load versions", "error"))
      .finally(() => setLoading(false));
  }, [selectedPromptId]);

  const handlePromptSelectorChange = (selection: { prompt_id: string; version?: number }) => {
    if (selection.prompt_id) {
      setSelectedPromptId(selection.prompt_id);
    }
    if (selection.version !== undefined) {
      setSelectedVersion(selection.version);
    }
  };

  const handleCreateNew = async () => {
    if (!selectedPromptId || editingVersion === null) {
      showNotification("Please select a prompt and version first", "error");
      return;
    }
    try {
      // Use the duplicate endpoint which correctly handles version incrementing
      // and copies all content from the source version
      const newVersion = await duplicate(selectedPromptId, editingVersion, {});
      // Reload versions to get the updated list
      const updatedVersions = await listVersions(selectedPromptId);
      setVersions(updatedVersions);
      // Select the new version
      setSelectedVersion(newVersion.version);
      showNotification(`Version v${newVersion.version} created successfully`, "success");
    } catch (err) {
      showNotification(`Failed to create new version: ${(err as Error).message}`, "error");
    }
  };

  // Sync runtimeVariables from metadata when loading a version
  const setSelectedVersionInternal = (version: number) => {
    setEditingVersion(version);
    const ver = versions.find((v: PromptVersion) => v.version === version);
    if (ver) {
      setEditForm({
        prompt_id: ver.prompt_id,
        version: ver.version,
        name: ver.name || "",
        intention: ver.intention || "",
        restrictions: ver.restrictions || "",
        output_structure: ver.output_structure || "",
        user_prompt_template: ver.user_prompt_template || "",
        is_default: ver.is_default || false,
        metadata: ver.metadata || undefined,
      });
      // Load runtime variables from metadata
      if (ver.metadata && typeof ver.metadata === "object" && "runtimeVariables" in ver.metadata) {
        setRuntimeVariables((ver.metadata.runtimeVariables as Record<string, string>) || {});
      } else {
        setRuntimeVariables({});
      }
    }
  };

  // Public setSelectedVersion that also updates runtime variables
  const setSelectedVersion = (version: number) => {
    setSelectedVersionInternal(version);
    // Also update editForm from the versions array (called by handlePromptSelectorChange)
    const ver = versions.find((v: PromptVersion) => v.version === version);
    if (ver) {
      setEditForm({
        prompt_id: ver.prompt_id,
        version: ver.version,
        name: ver.name || "",
        intention: ver.intention || "",
        restrictions: ver.restrictions || "",
        output_structure: ver.output_structure || "",
        user_prompt_template: ver.user_prompt_template || "",
        is_default: ver.is_default || false,
        metadata: ver.metadata || undefined,
      });
    }
  };

  // Override handleSave to persist runtimeVariables in metadata
  const handleSaveWithRuntimeVars = async () => {
    // Merge runtimeVariables into metadata before saving
    const baseMetadata = editForm.metadata || {};
    const metadataWithRuntimeVars = {
      ...baseMetadata,
      runtimeVariables,
    };

    if (!selectedPromptId || editingVersion === null) {
      showNotification("Missing prompt or version information", "error");
      return;
    }
    setSaving(true);
    try {
      const existing = versions.find((v: PromptVersion) => v.version === editingVersion);
      if (existing) {
        await updatePrompt(selectedPromptId, editingVersion, {
          name: editForm.name,
          intention: editForm.intention,
          restrictions: editForm.restrictions,
          output_structure: editForm.output_structure,
          user_prompt_template: editForm.user_prompt_template,
          metadata: metadataWithRuntimeVars,
        });
      } else {
        await createPrompt(selectedPromptId, {
          name: editForm.name,
          intention: editForm.intention,
          restrictions: editForm.restrictions,
          output_structure: editForm.output_structure,
          user_prompt_template: editForm.user_prompt_template,
          metadata: metadataWithRuntimeVars,
        });
        const updatedVersions = await listVersions(selectedPromptId);
        setVersions(updatedVersions);
        const def = updatedVersions.find((v: PromptVersion) => v.is_default);
        if (def) {
          setSelectedVersion(def.version);
        }
      }
      showNotification("Prompt saved successfully", "success");
      const updatedVersions = await listVersions(selectedPromptId);
      setVersions(updatedVersions);
      if (editingVersion !== null) {
        setSelectedVersion(editingVersion);
      }
    } catch (err) {
      showNotification(`Save failed: ${(err as Error).message}`, "error");
    } finally {
      setSaving(false);
    }
  };

  // Replace handleSave with the one that includes runtime variables
  const handleSave = handleSaveWithRuntimeVars;

  const handleSetDefault = async (version: number | null) => {
    if (!selectedPromptId || version === null) {
      showNotification("Please select a version first", "error");
      return;
    }
    try {
      await setDefaultPrompt(selectedPromptId, version);
      showNotification("Default version set successfully", "success");
      // Reload versions
      const updatedVersions = await listVersions(selectedPromptId);
      setVersions(updatedVersions);
      const def = updatedVersions.find((v: PromptVersion) => v.is_default);
      if (def) {
        setSelectedVersion(def.version);
      }
      // Refetch versions in the selector so the "(default)" label updates
      selectorRefetchRef.current?.();
    } catch (err) {
      showNotification(`Failed to set default: ${(err as Error).message}`, "error");
    }
  };

  const handleDelete = async () => {
    if (!selectedPromptId || editingVersion === null) {
      showNotification("Please select a version to delete", "error");
      return;
    }
    if (!confirm(`Are you sure you want to delete version ${editingVersion}?`)) {
      return;
    }
    try {
      await deletePrompt(selectedPromptId, editingVersion);
      showNotification("Version deleted successfully", "success");
      // Reload versions
      const updatedVersions = await listVersions(selectedPromptId);
      setVersions(updatedVersions);
      const def = updatedVersions.find((v: PromptVersion) => v.is_default);
      if (def) {
        setSelectedVersion(def.version);
      } else if (updatedVersions.length > 0) {
        setSelectedVersion(updatedVersions[0].version);
      } else {
        setEditingVersion(null);
      }
    } catch (err) {
      showNotification(`Delete failed: ${(err as Error).message}`, "error");
    }
  };

  const handlePreview = async () => {
    if (!selectedPromptId || editingVersion === null) {
      showNotification("Please select a version first", "error");
      return;
    }
    try {
      const result = await previewPrompt(selectedPromptId, editingVersion);
      setResolvedPreview({
        system: result.resolved_system_prompt,
        user: result.resolved_user_template,
      });
      setShowPreview(true);
    } catch (err) {
      showNotification(`Preview failed: ${(err as Error).message}`, "error");
    }
  };

  const combined = [editForm.intention, editForm.restrictions, editForm.output_structure].filter(Boolean).join("\n\n");
  return (
    <div className="space-y-6">
      <PageHeader title="Prompt Management" description="Manage and version your LLM prompt templates" />
      {toastMessage && <Toast message={toastMessage} type={toastType} onHidden={hideToast} />}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-4">
          {/* Hidden runtime variables input for the Save button to use */}
          <input
            type="hidden"
            value={JSON.stringify(runtimeVariables)}
            onChange={(e) => {
              try { setRuntimeVariables(JSON.parse(e.target.value)); } catch {}
            }}
          />
          <PromptSelector
            value={editingVersion !== null ? { prompt_id: selectedPromptId, version: editingVersion } : undefined}
            onChange={handlePromptSelectorChange}
            refetchRef={selectorRefetchRef}
          />
          <Card>
            <div className="space-y-4">
               <PromptEditorSection
                  label="Intention"
                  value={editForm.intention}
                  onChange={(v) => setEditForm({ ...editForm, intention: v })}
                  onImprove={() => { setImprovingSection("intention"); setShowImprovementChat(true); }}
                  onClone={() => { setCloningSection("intention"); setShowCloneModal(true); }}
                />
               <PromptEditorSection
                  label="Restrictions"
                  value={editForm.restrictions}
                  onChange={(v) => setEditForm({ ...editForm, restrictions: v })}
                  onImprove={() => { setImprovingSection("restrictions"); setShowImprovementChat(true); }}
                  onClone={() => { setCloningSection("restrictions"); setShowCloneModal(true); }}
                />
               <PromptEditorSection
                  label="Output Structure"
                  value={editForm.output_structure}
                  onChange={(v) => setEditForm({ ...editForm, output_structure: v })}
                  onImprove={() => { setImprovingSection("output_structure"); setShowImprovementChat(true); }}
                  onClone={() => { setCloningSection("output_structure"); setShowCloneModal(true); }}
                />
               <PromptEditorSection
                  label="User Prompt Template"
                  value={editForm.user_prompt_template}
                  onChange={(v) => setEditForm({ ...editForm, user_prompt_template: v })}
                  onImprove={() => { setImprovingSection("user_prompt_template"); setShowImprovementChat(true); }}
                  onClone={() => { setCloningSection("user_prompt_template"); setShowCloneModal(true); }}
                />
              <div className="flex gap-2">
                <Button variant="primary" onClick={handleSave} disabled={saving}>{saving ? "Saving..." : "Save"}</Button>
                <Button variant="ghost" onClick={() => { const v = versions.find((p) => p.version === editingVersion); if (v) setSelectedVersion(v.version); else setEditingVersion(null); }}>Cancel</Button>
                <Button variant="secondary" onClick={() => handleSetDefault(editingVersion)}>Set Default</Button>
                <Button variant="danger" onClick={handleDelete}>Delete</Button>
                <Button variant="accent" onClick={handlePreview}>Preview Rendered</Button>
                <Button variant="primary" onClick={handleCreateNew}>+ New Version</Button>
                <Button variant="accent" onClick={() => setShowCreateModal(true)}>+ New Prompt</Button>
              </div>
              {showPreview && resolvedPreview && <PreviewPanel before={combined} after={resolvedPreview.system} />}
            </div>
          </Card>
        </div>
          <div className="lg:col-span-1">
            <PlaceholderPalette
              placeholders={placeholders}
              userPromptTemplate={editForm.user_prompt_template}
              runtimeVariables={runtimeVariables}
              onRuntimeVariablesChange={setRuntimeVariables}
            />
          </div>
      </div>

      {/* Create Prompt Modal */}
      <CreatePromptModal
        open={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onCreate={async (promptId: string) => {
          showNotification(`Prompt "${promptId}" created successfully`, "success");
          // Reload all prompts and select the new one
          const updated = await listAllPrompts();
          setAllPrompts(updated);
          setSelectedPromptId(promptId);
          // Load versions of the new prompt
          const newVersions = await listVersions(promptId);
          setVersions(newVersions);
          if (newVersions.length > 0) {
            const v = newVersions[0];
            setEditingVersion(v.version);
            setEditForm({
              prompt_id: v.prompt_id,
              version: v.version,
              name: v.name || "",
              intention: v.intention || "",
              restrictions: v.restrictions || "",
              output_structure: v.output_structure || "",
              user_prompt_template: v.user_prompt_template || "",
              is_default: v.is_default || false,
              metadata: v.metadata || undefined,
            });
          }
        }}
      />

      {/* AI Improvement Chat */}
      <PromptImprovementChat
        section={improvingSection}
        currentText={
          improvingSection === "intention" ? editForm.intention :
          improvingSection === "restrictions" ? editForm.restrictions :
          improvingSection === "output_structure" ? editForm.output_structure :
          editForm.user_prompt_template
        }
        open={showImprovementChat}
        onClose={() => setShowImprovementChat(false)}
        onApply={(improvedText: string) => {
          setEditForm({
            ...editForm,
            [improvingSection]: improvedText,
          });
          showNotification(`${improvingSection.replace('_', ' ')} improved successfully`, "success");
        }}
      />

      {/* Clone Section Modal */}
      <CloneSectionModal
        open={showCloneModal}
        section={cloningSection}
        sectionLabel={
          cloningSection === "intention" ? "Intention" :
          cloningSection === "restrictions" ? "Restrictions" :
          cloningSection === "output_structure" ? "Output Structure" :
          "User Prompt Template"
        }
        currentPromptId={selectedPromptId}
        currentVersion={editingVersion ?? 1}
        onClose={() => setShowCloneModal(false)}
        onClone={(text: string) => {
          setEditForm({
            ...editForm,
            [cloningSection]: text,
          });
          showNotification(`${cloningSection.replace('_', ' ')} cloned successfully`, "success");
        }}
      />
    </div>
  );
}
