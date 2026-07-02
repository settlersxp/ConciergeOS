import { useState } from "react";
import { guestSearchApi } from "../services/api";
import type { GuestSearchResponse } from "../types";
import {
  PageHeader,
  Card,
  FormField,
  Input,
  Button,
  Toast,
  Badge,
  RegionSelector,
} from "../components/ui";
import PromptSelector from "../components/ui/PromptSelector";
import { useMediaExtraction } from "../hooks/useMediaExtraction";

export default function GuestSearch() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<GuestSearchResponse | null>(null);
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" | "info" } | null>(null);
  const [selectedPrompt, setSelectedPrompt] = useState<{ prompt_id: string; version?: number }>({
    prompt_id: "guest-search",
  });

  // Runtime variable key (pre-populated for easy editing)
  const [runtimeVarKey] = useState("customer_name");

  // Build runtime variables from the current query
  const runtimeVariables: Record<string, string> = query.trim()
    ? { [runtimeVarKey]: query.trim() }
    : {};

  // ── Media state (shared hook) ──────────────────────────────────────
  const media = useMediaExtraction((name: string) => {
    setQuery(name);
    setToast({ message: `Name extracted: "${name}"`, type: "success" });
  });

  // ── Helpers: Detect supported MIME type for MediaRecorder ──────────
  // (Still needed since the hook uses a simpler approach; kept here
  //  for the native MediaRecorder fallback if needed)

  // ── Handlers: Search ───────────────────────────────────────────────

  const handleSearch = async () => {
    if (!query.trim()) {
      setToast({ message: "Please enter a customer name", type: "error" });
      return;
    }
    setLoading(true);
    setResult(null);
    try {
      const data = await guestSearchApi.search(query, {
        prompt_id: selectedPrompt.prompt_id,
        version: selectedPrompt.version,
        runtime_variables: runtimeVariables,
      });
      setResult(data);
    } catch (e: unknown) {
      setToast({ message: e instanceof Error ? e.message : "Search failed", type: "error" });
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleSearch();
  };

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <PageHeader
        title="Guest Search"
        description="Search for guests using the LLM-powered query system."
      />

      {/* ── Media Input Section ────────────────────────────────────── */}
      <Card title="Name Input" className="mb-6">
        {/* Hidden file inputs */}
        <input
          ref={media.imageInputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={media.handleImageChange}
        />
        <input
          ref={media.cameraInputRef}
          type="file"
          accept="image/*"
          capture="environment"
          className="hidden"
          onChange={media.handleImageChange}
        />

        <div className="flex flex-wrap gap-3">
          <Button variant="secondary" onClick={media.handleUploadPhoto}>
            Upload Photo
          </Button>

          <Button variant="secondary" onClick={media.handleTakePhoto}>
            Take Photo
          </Button>

          {media.isRecording ? (
            <Button variant="danger" onClick={media.handleStopRecording}>
              Stop Recording
            </Button>
          ) : (
            <Button variant="secondary" onClick={media.handleSpeakName}>
              Speak Name
            </Button>
          )}

          {media.mediaMode !== "none" && (
            <Button variant="ghost" onClick={media.handleClear}>
              Clear
            </Button>
          )}
        </div>

        {/* Image preview with region selector */}
        {media.selectedImage && (
          <div className="mt-4">
            <RegionSelector
              imageUrl={media.selectedImage}
              alt="Image preview"
              onRegionChange={() => {}}
            />
            <div className="mt-3 flex justify-end">
              <Button
                variant="primary"
                loading={media.extracting}
                onClick={() => media.handleExtractName()}
              >
                Extract Name
              </Button>
            </div>
          </div>
        )}

        {/* Audio recording feedback */}
        {media.recordedAudio && (
          <div className="mt-4">
            {media.isRecording ? (
              <div className="flex items-center gap-2 text-sm text-red-600">
                <span className="inline-block h-3 w-3 rounded-full bg-red-500 animate-pulse" />
                Recording...
              </div>
            ) : (
              <div className="space-y-2">
                <audio src={media.recordedAudio} controls className="w-full" />
                <div className="flex justify-end">
                  <Button
                    variant="primary"
                    loading={media.extracting}
                    onClick={() => media.handleExtractName()}
                  >
                    Extract Name
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Extraction error */}
        {media.extractError && (
          <div className="mt-4 p-3 bg-accent-50 border border-accent-200 rounded-md dark:bg-accent-900/30 dark:border-accent-800">
            <p className="text-sm font-medium text-accent-900 dark:text-accent-300">
              Extraction Error: {media.extractError}
            </p>
          </div>
        )}
      </Card>

      {/* ── Prompt + Name Input ────────────────────────────────────── */}
      <Card>
        <div className="mt-4">
          <PromptSelector
            value={selectedPrompt}
            onChange={setSelectedPrompt}
            label="Prompt Version"
          />
        </div>

        <div className="mt-4">
          <FormField htmlFor="guestQuery" label="Customer Name">
            <Input
              id="guestQuery"
              type="text"
              placeholder="e.g. عائشة إبراهيم"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
            />
          </FormField>
        </div>

        <div className="mt-4 flex justify-end">
          <Button variant="primary" loading={loading} onClick={handleSearch}>
            Search
          </Button>
        </div>
      </Card>

      {/* ── Results ────────────────────────────────────────────────── */}
      {result && (
        <Card title="Search Result" className="mt-6">
          {result.cached !== undefined && result.cached && (
            <div className="mb-2">
              <Badge variant="info">Cached</Badge>
            </div>
          )}
          <div className="mt-4 whitespace-pre-wrap text-sm text-primary-800 dark:text-primary-200">
            {result.llm_response}
          </div>
        </Card>
      )}

      {toast && (
        <Toast message={toast.message} type={toast.type} onHidden={() => setToast(null)} />
      )}
    </div>
  );
}