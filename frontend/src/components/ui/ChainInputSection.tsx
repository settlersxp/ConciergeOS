import React, { useState, useCallback, useRef } from "react";
import type { PromptGroupItem } from "../../types/prompt";
import Button from "./Button";
import Input from "./Input";
import Card from "./Card";
import FormField from "./FormField";
import { RegionSelector } from "./RegionSelector";
import { guestSearchApi, type CropRegion } from "../../services/api";

// Known static placeholders that should not be turned into input fields
const KNOWN_PLACEHOLDERS = new Set([
  "DATABASE_TABLES",
  "GUEST_INFORMATION",
  "ROOM_INFORMATION",
  "CURRENT_DATE",
  "AVAILABLE_TOOLS",
]);

/**
 * Infer field names from a prompt template string.
 * Filters out chain result placeholders ({step_N}), static placeholders, and table.field patterns.
 */
export function inferInputFields(template: string): InputField[] {
  const patterns: InputField[] = [];
  const regex = /\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(template)) !== null) {
    const name = match[1];
    if (name.startsWith("step_")) continue;
    if (KNOWN_PLACEHOLDERS.has(name.toUpperCase())) continue;
    if (name.includes(".")) continue;
    patterns.push({
      name,
      label: name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
      type: inferFieldType(name),
    });
  }
  return patterns;
}

function inferFieldType(name: string): "text" | "date" | "select" {
  if (name.includes("date") || name.includes("time")) return "date";
  if (name.includes("filter") || name.includes("status") || name.includes("type")) return "select";
  return "text";
}

export interface InputField {
  name: string;
  label: string;
  type: "text" | "date" | "select";
}

export interface ChainInputSectionProps {
  step: PromptGroupItem;
  template: string;
  inputs: Record<string, string>;
  onInputChange: (name: string, value: string) => void;
  onRun: (inputs: Record<number, Record<string, string>>, initialInput?: string) => void;
  loading: boolean;
}

/**
 * ChainInputSection renders the input fields for the first step of a PromptChainPage.
 * It parses the step's user_prompt_template for {placeholder} patterns, generates
 * appropriate input fields, and includes media input (photo/voice) from GuestSearch.
 */
export default function ChainInputSection({
  step,
  template,
  inputs,
  onInputChange,
  onRun,
  loading,
}: ChainInputSectionProps) {
  const [extractedName, setExtractedName] = useState<string>("");
  const [extracting, setExtracting] = useState(false);
  const [extractError, setExtractError] = useState<string | null>(null);
  const [selectedImage, setSelectedImage] = useState<string | null>(null);
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [recordedAudio, setRecordedAudio] = useState<string | null>(null);
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [cropRegion, setCropRegion] = useState<CropRegion | null>(null);

  const imageInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  // Parse template for placeholder fields
  const fields = inferInputFields(template);

  // --- Photo Upload ---
  const handleUploadPhoto = useCallback(() => {
    imageInputRef.current?.click();
  }, []);

  const handleTakePhoto = useCallback(() => {
    cameraInputRef.current?.click();
  }, []);

  const handleImageChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;
      setImageFile(file);
      setAudioFile(null);
      setRecordedAudio(null);
      setCropRegion(null);
      setExtractedName("");
      setExtractError(null);
      const reader = new FileReader();
      reader.onload = (ev) => {
        setSelectedImage(ev.target?.result as string);
      };
      reader.readAsDataURL(file);
    },
    [],
  );

  const handleClearImage = useCallback(() => {
    setSelectedImage(null);
    setImageFile(null);
    setCropRegion(null);
    setExtractedName("");
    setExtractError(null);
    if (imageInputRef.current) imageInputRef.current.value = "";
    if (cameraInputRef.current) cameraInputRef.current.value = "";
  }, []);

  // --- Voice Recording ---
  const handleSpeakName = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioChunksRef.current = [];
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (e) => {
        audioChunksRef.current.push(e.data);
      };

      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: "audio/webm" });
        // Determine file extension from MIME type
        let ext = "webm";
        if (mediaRecorder.mimeType.includes("mp4")) ext = "m4a";
        setAudioFile(new File([audioBlob], `recording.${ext}`, { type: mediaRecorder.mimeType || "audio/webm" }));
        setImageFile(null);
        setSelectedImage(null);
        setCropRegion(null);
        setExtractedName("");
        setExtractError(null);
        const reader = new FileReader();
        reader.onload = () => {
          setRecordedAudio(reader.result as string);
        };
        reader.readAsDataURL(audioBlob);
        stream.getTracks().forEach((t) => t.stop());
      };

      mediaRecorder.start();
      setIsRecording(true);
    } catch (err) {
      console.error("Microphone access denied:", err);
    }
  }, []);

  const handleStopRecording = useCallback(() => {
    if (mediaRecorderRef.current?.state === "recording") {
      mediaRecorderRef.current.stop();
    }
    setIsRecording(false);
  }, []);

  // --- Name Extraction ---
  const handleExtractName = useCallback(async () => {
    setExtractError(null);

    if (imageFile) {
      setExtracting(true);
      try {
        const data = await guestSearchApi.extractName(imageFile, cropRegion || undefined);
        setExtractedName(data.extracted_name);
        onInputChange("customer_name", data.extracted_name);
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : "Extraction failed";
        setExtractError(msg);
      } finally {
        setExtracting(false);
      }
    } else if (audioFile) {
      setExtracting(true);
      try {
        const data = await guestSearchApi.extractName(audioFile);
        setExtractedName(data.extracted_name);
        onInputChange("customer_name", data.extracted_name);
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : "Extraction failed";
        setExtractError(msg);
      } finally {
        setExtracting(false);
      }
    } else {
      setExtractError("Please upload an image or record audio first");
    }
  }, [imageFile, audioFile, cropRegion, onInputChange]);

  const handleClear = useCallback(() => {
    setExtractedName("");
    setExtractError(null);
    setSelectedImage(null);
    setImageFile(null);
    setRecordedAudio(null);
    setAudioFile(null);
    setCropRegion(null);
    if (imageInputRef.current) imageInputRef.current.value = "";
    if (cameraInputRef.current) cameraInputRef.current.value = "";
    onInputChange("customer_name", "");
  }, [onInputChange]);

  // Collect all current inputs for step 1
  const step1Inputs: Record<string, string> = { ...inputs };

  const handleSubmit = () => {
    onRun({ 1: step1Inputs }, step1Inputs.customer_name);
  };

  return (
    <Card title="Step 1: Input" titleClassName="text-xl">
      {/* Hidden file inputs for photo upload and camera capture */}
      <input
        ref={imageInputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={handleImageChange}
      />
      <input
        ref={cameraInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={handleImageChange}
      />

      {/* Template-derived input fields */}
      <div className="space-y-4">
        {fields.length > 0 ? (
          fields.map((field) => (
            <FormField key={field.name} label={field.label}>
              {field.type === "text" ? (
                <Input
                  type="text"
                  value={inputs[field.name] || ""}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                    onInputChange(field.name, e.target.value)
                  }
                />
              ) : field.type === "date" ? (
                <Input
                  type="date"
                  value={inputs[field.name] || ""}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                    onInputChange(field.name, e.target.value)
                  }
                />
              ) : (
                <select
                  value={inputs[field.name] || ""}
                  onChange={(e: React.ChangeEvent<HTMLSelectElement>) =>
                    onInputChange(field.name, e.target.value)
                  }
                  className="w-full rounded-md border border-surface-300 bg-white px-3 py-2 text-sm text-primary-800 focus:border-secondary-400 focus:outline-none focus:ring-2 focus:ring-secondary-400/20 dark:border-primary-600 dark:bg-primary-700 dark:text-white"
                >
                  <option value="">Select...</option>
                  <option value="active">Active</option>
                  <option value="inactive">Inactive</option>
                  <option value="all">All</option>
                </select>
              )}
            </FormField>
          ))
        ) : (
          <p className="text-sm text-primary-500 dark:text-primary-400 italic">
            No template fields detected. Use the media input below or type directly.
          </p>
        )}
      </div>

      {/* Media input section */}
      <div className="mt-6 border-t border-surface-200 dark:border-primary-700 pt-4">
        <h3 className="text-sm font-medium text-primary-700 dark:text-primary-300 mb-2">Media Input</h3>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={handleUploadPhoto}>
            📷 Upload Photo
          </Button>
          <Button variant="secondary" onClick={handleTakePhoto}>
            📸 Take Photo
          </Button>
          {isRecording ? (
            <Button variant="primary" onClick={handleStopRecording}>
              ⏹ Stop Recording
            </Button>
          ) : (
            <Button variant="secondary" onClick={handleSpeakName}>
              🎤 Speak Name
            </Button>
          )}
          {(imageFile || audioFile) && (
            <Button variant="ghost" onClick={handleClear}>
              Clear
            </Button>
          )}
        </div>
      </div>

      {/* Image preview with region selector */}
      {selectedImage && (
        <div className="mt-4">
          <RegionSelector
            imageUrl={selectedImage}
            alt="Image preview"
            onRegionChange={setCropRegion}
          />
          {cropRegion && (
            <div className="mt-2 flex justify-end">
              <Button
                variant="primary"
                loading={extracting}
                onClick={handleExtractName}
              >
                Extract Name
              </Button>
            </div>
          )}
          <div className="mt-1 text-xs text-primary-400 dark:text-primary-500 text-center">
            Click and drag to select the name region, then click Extract Name
          </div>
        </div>
      )}

      {/* Audio playback */}
      {recordedAudio && (
        <div className="mt-4">
          <p className="text-sm text-primary-600 dark:text-primary-400 mb-1">Recorded audio:</p>
          <audio controls src={recordedAudio} className="w-full" />
          <div className="mt-2 flex justify-end">
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

      {/* Extraction error */}
      {extractError && (
        <div className="mt-4 p-3 bg-accent-50 border border-accent-200 rounded-md dark:bg-accent-900/30 dark:border-accent-800">
          <p className="text-sm font-medium text-accent-900 dark:text-accent-300">
            Extraction Error: {extractError}
          </p>
        </div>
      )}

      {/* Extracted name display */}
      {extractedName && (
        <div className="mt-4 p-3 bg-primary-50 border border-primary-200 rounded-md dark:bg-primary-900/30 dark:border-primary-700">
          <p className="text-sm font-medium text-primary-900 dark:text-primary-200">
            Extracted Name: {extractedName}
          </p>
        </div>
      )}

      {/* Run button */}
      <div className="mt-6 flex items-center gap-3">
        <Button
          variant="primary"
          onClick={handleSubmit}
          loading={loading}
          disabled={loading}
        >
          Search
        </Button>
        <Button variant="ghost" onClick={handleExtractName} disabled={loading}>
          🔍 Extract Name
        </Button>
      </div>
    </Card>
  );
}
