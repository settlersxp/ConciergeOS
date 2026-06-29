import { useRef, useState } from "react";
import { guestSearchApi, type CropRegion } from "../services/api";
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

export default function GuestSearch() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<GuestSearchResponse | null>(null);
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" | "info" } | null>(null);
  const [selectedPrompt, setSelectedPrompt] = useState<{ prompt_id: string; version?: number }>({
    prompt_id: "guest-search",
  });

  // Runtime variable key (pre-populated for easy editing)
  const [runtimeVarKey, setRuntimeVarKey] = useState("customer_name");

  // Build runtime variables from the current query
  const runtimeVariables: Record<string, string> = query.trim()
    ? { [runtimeVarKey]: query.trim() }
    : {};

  // ── Media state ──────────────────────────────────────────────────────
  const [mediaMode, setMediaMode] = useState<"none" | "image" | "audio">("none");
  const [imagePreviewUrl, setImagePreviewUrl] = useState<string>("");
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [cropRegion, setCropRegion] = useState<CropRegion | null>(null);
  const [extracting, setExtracting] = useState(false);

  // Audio recording state
  const [isRecording, setIsRecording] = useState(false);
  const [audioRecordingUrl, setAudioRecordingUrl] = useState<string>("");
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  // Hidden file input refs
  const imageInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);

  // ── Handlers: Media input ────────────────────────────────────────────

  const handleImageSelect = (file: File) => {
    setImageFile(file);
    setImagePreviewUrl(URL.createObjectURL(file));
    setMediaMode("image");
    setCropRegion(null);
  };

  const handleImageInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleImageSelect(file);
    // Reset input so the same file can be re-selected
    e.target.value = "";
  };

  const handleCameraCapture = () => {
    cameraInputRef.current?.click();
  };

  const handleCameraInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleImageSelect(file);
    e.target.value = "";
  };

  // ── Handlers: Voice recording ────────────────────────────────────────

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];

      recorder.ondataavailable = (evt) => {
        if (evt.data.size > 0) chunksRef.current.push(evt.data);
      };

      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        const url = URL.createObjectURL(blob);
        setAudioRecordingUrl(url);
        setMediaMode("audio");
        setAudioFile(new File([blob], "recording.webm", { type: "audio/webm" }));
      };

      recorder.start();
      mediaRecorderRef.current = recorder;
      setIsRecording(true);
      setAudioRecordingUrl("");
      setAudioFile(null);
      setMediaMode("audio");
    } catch (e: unknown) {
      setToast({
        message: e instanceof Error ? e.message : "Microphone access denied",
        type: "error",
      });
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  // ── Handlers: Extract name ───────────────────────────────────────────

  const handleExtractName = async () => {
    // Determine which source to use
    if (mediaMode === "image" && imageFile) {
      setExtracting(true);
      try {
        const resp = await guestSearchApi.extractName(imageFile, cropRegion ?? undefined);
        setQuery(resp.extracted_name);
        setToast({ message: `Name extracted from ${resp.source}: "${resp.extracted_name}"`, type: "success" });
      } catch (e: unknown) {
        setToast({ message: e instanceof Error ? e.message : "Extraction failed", type: "error" });
      } finally {
        setExtracting(false);
      }
    } else if (mediaMode === "audio" && audioFile) {
      setExtracting(true);
      try {
        const resp = await guestSearchApi.extractName(audioFile);
        setQuery(resp.extracted_name);
        setToast({ message: `Name extracted from ${resp.source}: "${resp.extracted_name}"`, type: "success" });
      } catch (e: unknown) {
        setToast({ message: e instanceof Error ? e.message : "Extraction failed", type: "error" });
      } finally {
        setExtracting(false);
      }
    } else {
      setToast({ message: "Please upload an image or record audio first", type: "error" });
    }
  };

  const clearMedia = () => {
    setMediaMode("none");
    setImageFile(null);
    setAudioFile(null);
    setCropRegion(null);
    if (imagePreviewUrl) URL.revokeObjectURL(imagePreviewUrl);
    if (audioRecordingUrl) URL.revokeObjectURL(audioRecordingUrl);
    setImagePreviewUrl("");
    setAudioRecordingUrl("");
  };

  // ── Handlers: Search ─────────────────────────────────────────────────

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

      {/* ── Media Input Section ──────────────────────────────────────── */}
      <Card title="Name Input" className="mb-6">
        <div className="flex flex-wrap gap-3">
          <input
            ref={imageInputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={handleImageInputChange}
          />
          <Button
            variant="secondary"
            onClick={() => imageInputRef.current?.click()}
          >
            Upload Photo
          </Button>

          <input
            ref={cameraInputRef}
            type="file"
            accept="image/*"
            capture="environment"
            className="hidden"
            onChange={handleCameraInputChange}
          />
          <Button
            variant="secondary"
            onClick={handleCameraCapture}
          >
            Take Photo
          </Button>

          {isRecording ? (
            <Button variant="danger" onClick={stopRecording}>
              Stop Recording
            </Button>
          ) : (
            <Button variant="secondary" onClick={startRecording}>
              Speak Name
            </Button>
          )}

          {mediaMode !== "none" && (
            <Button variant="ghost" onClick={clearMedia}>
              Clear
            </Button>
          )}
        </div>

        {/* Image preview with region selector */}
        {mediaMode === "image" && imagePreviewUrl && (
          <div className="mt-4">
            <RegionSelector
              imageUrl={imagePreviewUrl}
              alt="Image preview"
              onRegionChange={setCropRegion}
            />
            <div className="mt-3 flex justify-end">
              <Button
                variant="primary"
                loading={extracting}
                onClick={handleExtractName}
              >
                Extract Name
              </Button>
            </div>
          </div>
        )}

        {/* Audio recording feedback */}
        {mediaMode === "audio" && (
          <div className="mt-4">
            {isRecording ? (
              <div className="flex items-center gap-2 text-sm text-red-600">
                <span className="inline-block h-3 w-3 rounded-full bg-red-500 animate-pulse" />
                Recording...
              </div>
            ) : audioRecordingUrl ? (
              <div className="space-y-2">
                <audio src={audioRecordingUrl} controls className="w-full" />
                <div className="flex justify-end">
                  <Button
                    variant="primary"
                    loading={extracting}
                    onClick={handleExtractName}
                  >
                    Extract Name
                  </Button>
                </div>
              </div>
            ) : null}
          </div>
        )}
      </Card>

      {/* ── Prompt + Name Input ──────────────────────────────────────── */}
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

      {/* ── Results ──────────────────────────────────────────────────── */}
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