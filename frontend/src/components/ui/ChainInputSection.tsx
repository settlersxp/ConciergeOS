import React, { useState, useCallback, useRef } from "react";
import type { PromptGroupItem } from "../../types/prompt";
import Button from "./Button";
import Input from "./Input";

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
  const [selectedImage, setSelectedImage] = useState<string | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [recordedAudio, setRecordedAudio] = useState<string | null>(null);

  const imageInputRef = useRef<HTMLInputElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  // Parse template for placeholder fields
  const fields = inferInputFields(template);

  // --- Photo Upload ---
  const handleUploadPhoto = useCallback(() => {
    imageInputRef.current?.click();
  }, []);

  const handleImageChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (ev) => {
        setSelectedImage(ev.target?.result as string);
        setRecordedAudio(null);
      };
      reader.readAsDataURL(file);
    },
    [],
  );

  const handleClearImage = useCallback(() => {
    setSelectedImage(null);
    if (imageInputRef.current) imageInputRef.current.value = "";
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
        const reader = new FileReader();
        reader.onload = () => {
          setRecordedAudio(reader.result as string);
          setSelectedImage(null);
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
    // In production, this would call /api/guest-search/extract-name with the image/audio
    // For now, simulate extraction
    const simulatedName = `Guest_${Math.floor(Math.random() * 1000)}`;
    setExtractedName(simulatedName);
    onInputChange("customer_name", simulatedName);
  }, [onInputChange]);

  const handleClear = useCallback(() => {
    setExtractedName("");
    setSelectedImage(null);
    setRecordedAudio(null);
    if (imageInputRef.current) imageInputRef.current.value = "";
    onInputChange("customer_name", "");
  }, [onInputChange]);

  // Collect all current inputs for step 1
  const step1Inputs: Record<string, string> = { ...inputs };

  const handleSubmit = () => {
    onRun({ 1: step1Inputs }, step1Inputs.customer_name);
  };

  return (
    <div className="bg-white shadow rounded-lg p-6">
      <h2 className="text-xl font-semibold text-gray-900 mb-4">
        Step 1: Input
      </h2>

      {/* Hidden file input for photo upload */}
      <input
        ref={imageInputRef}
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
            <div key={field.name}>
              <label className="block text-sm font-medium text-gray-700">
                {field.label}
              </label>
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
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                >
                  <option value="">Select...</option>
                  <option value="active">Active</option>
                  <option value="inactive">Inactive</option>
                  <option value="all">All</option>
                </select>
              )}
            </div>
          ))
        ) : (
          <p className="text-sm text-gray-500 italic">
            No template fields detected. Use the media input below or type directly.
          </p>
        )}
      </div>

      {/* Media input section */}
      <div className="mt-6 border-t border-gray-200 pt-4">
        <h3 className="text-sm font-medium text-gray-700 mb-2">Media Input</h3>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={handleUploadPhoto}>
            📷 Upload Photo
          </Button>
          <Button variant="secondary" onClick={handleUploadPhoto}>
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
          <Button variant="ghost" onClick={handleClear}>
            Clear
          </Button>
        </div>
      </div>

      {/* Image preview */}
      {selectedImage && (
        <div className="mt-4">
          <div className="relative rounded-lg overflow-hidden border border-gray-200">
            <img
              src={selectedImage}
              alt="Uploaded"
              className="w-full max-h-48 object-cover"
            />
            <button
              onClick={handleClearImage}
              className="absolute top-1 right-1 bg-black/50 text-white text-xs px-2 py-1 rounded"
            >
              ✕
            </button>
          </div>
        </div>
      )}

      {/* Audio playback */}
      {recordedAudio && (
        <div className="mt-4">
          <p className="text-sm text-gray-600 mb-1">Recorded audio:</p>
          <audio controls src={recordedAudio} className="w-full" />
        </div>
      )}

      {/* Extracted name display */}
      {extractedName && (
        <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-md">
          <p className="text-sm font-medium text-blue-900">
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
    </div>
  );
}
