import React from "react";
import type { PromptGroupItem } from "../../types/prompt";
import Button from "./Button";
import Input from "./Input";
import Card from "./Card";
import FormField from "./FormField";
import { RegionSelector } from "./RegionSelector";
import { useMediaExtraction } from "../../hooks/useMediaExtraction";
import { inferInputFields } from "../../utils/inputFields";

export interface ChainInputSectionProps {
  step: PromptGroupItem;
  template: string;
  inputs: Record<string, string>;
  onInputChange: (name: string, value: string) => void;
  onRun: (inputs: Record<number, Record<string, string>>, initialInput?: string) => void;
  loading: boolean;
}

/**
 * ChainInputSection renders the input fields for a chain step.
 * It parses the step's user_prompt_template for {placeholder} patterns,
 * generates appropriate input fields, and includes media input for name extraction.
 *
 * Uses:
 * - inferInputFields() from shared utilities for template parsing
 * - useMediaExtraction() hook for photo/voice/recording/extraction logic
 */
export default function ChainInputSection({
  step: _step,
  template,
  inputs,
  onInputChange,
  onRun,
  loading,
}: ChainInputSectionProps) {
  // Parse template for placeholder fields (shared utility)
  const fields = inferInputFields(template);

  // Media extraction (shared hook)
  const media = useMediaExtraction((name: string) => {
    onInputChange("customer_name", name);
  });

  const handleSubmit = () => {
    onRun({ 1: { ...inputs } }, inputs.customer_name);
  };

  return (
    <Card title="Step 1: Input" titleClassName="text-xl">
      {/* Hidden file inputs for photo upload and camera capture */}
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
          <Button variant="secondary" onClick={media.handleUploadPhoto}>
            Upload Photo
          </Button>
          <Button variant="secondary" onClick={media.handleTakePhoto}>
            Take Photo
          </Button>
          {media.isRecording ? (
            <Button variant="primary" onClick={media.handleStopRecording}>
              Stop Recording
            </Button>
          ) : (
            <Button variant="secondary" onClick={media.handleSpeakName}>
              Speak Name
            </Button>
          )}
          {media.mediaMode !== "none" && (
            <Button variant="ghost" onClick={() => media.handleClear(() => onInputChange("customer_name", ""))}>
              Clear
            </Button>
          )}
        </div>
      </div>

      {/* Image preview with region selector */}
      {media.selectedImage && (
        <div className="mt-4">
          <RegionSelector
            imageUrl={media.selectedImage}
            alt="Image preview"
            onRegionChange={() => {}}
          />
          {media.cropRegion && (
            <div className="mt-2 flex justify-end">
              <Button
                variant="primary"
                loading={media.extracting}
                onClick={() => media.handleExtractName()}
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
      {media.recordedAudio && (
        <div className="mt-4">
          <p className="text-sm text-primary-600 dark:text-primary-400 mb-1">Recorded audio:</p>
          <audio controls src={media.recordedAudio} className="w-full" />
          <div className="mt-2 flex justify-end">
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

      {/* Extraction error */}
      {media.extractError && (
        <div className="mt-4 p-3 bg-accent-50 border border-accent-200 rounded-md dark:bg-accent-900/30 dark:border-accent-800">
          <p className="text-sm font-medium text-accent-900 dark:text-accent-300">
            Extraction Error: {media.extractError}
          </p>
        </div>
      )}

      {/* Extracted name display */}
      {media.extractedName && (
        <div className="mt-4 p-3 bg-primary-50 border border-primary-200 rounded-md dark:bg-primary-900/30 dark:border-primary-700">
          <p className="text-sm font-medium text-primary-900 dark:text-primary-200">
            Extracted Name: {media.extractedName}
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
        <Button variant="ghost" onClick={() => media.handleExtractName()} disabled={loading}>
          Extract Name
        </Button>
      </div>
    </Card>
  );
}