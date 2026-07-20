/**
 * Hook that encapsulates all multimodal name extraction logic:
 * photo upload, camera capture, voice recording, region selection,
 * and LLM-based name extraction via the /api/guest-search/extract-name endpoint.
 *
 * Shared between GuestSearch and ChainInputSection to eliminate duplication.
 */

import { useState, useCallback, useRef } from "react";
import { guestSearchApi, type CropRegion } from "../services/api";

export interface MediaExtractionState {
  // Image state
  selectedImage: string | null;
  imageFile: File | null;
  // Audio state
  recordedAudio: string | null;
  audioFile: File | null;
  // Extraction state
  isRecording: boolean;
  cropRegion: CropRegion | null;
  extractedName: string;
  extracting: boolean;
  extractError: string | null;
  // Mode
  mediaMode: "none" | "image" | "audio";
}

export interface MediaExtractionHandlers {
  // Photo
  handleUploadPhoto: () => void;
  handleTakePhoto: () => void;
  handleImageChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  handleClearImage: () => void;
  // Voice
  handleSpeakName: () => void;
  handleStopRecording: () => void;
  // Extraction
  handleExtractName: (onPopulate?: (name: string) => void) => void;
  // Clear all
  handleClear: (onClear?: () => void) => void;
  // Refs for hidden file inputs
  imageInputRef: React.RefObject<HTMLInputElement | null>;
  cameraInputRef: React.RefObject<HTMLInputElement | null>;
}

export function useMediaExtraction(
  onNameExtracted?: (name: string) => void,
  modelId?: number,
): MediaExtractionState & MediaExtractionHandlers {
  const [selectedImage, setSelectedImage] = useState<string | null>(null);
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [recordedAudio, setRecordedAudio] = useState<string | null>(null);
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [cropRegion, setCropRegion] = useState<CropRegion | null>(null);
  const [extractedName, setExtractedName] = useState<string>("");
  const [extracting, setExtracting] = useState(false);
  const [extractError, setExtractError] = useState<string | null>(null);
  const [mediaMode, setMediaMode] = useState<"none" | "image" | "audio">("none");

  const imageInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  // ── Photo Upload ────────────────────────────────────────────────────

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
      setMediaMode("image");
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
    setMediaMode("none");
    if (imageInputRef.current) imageInputRef.current.value = "";
    if (cameraInputRef.current) cameraInputRef.current.value = "";
  }, []);

  // ── Voice Recording ─────────────────────────────────────────────────

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
        const mimeType = mediaRecorder.mimeType || "audio/webm";
        const audioBlob = new Blob(audioChunksRef.current, { type: mimeType });
        let ext = "webm";
        if (mimeType.includes("mp4") || mimeType.includes("mp3")) ext = "mp4";
        else if (mimeType.includes("ogg")) ext = "ogg";
        else if (mimeType.includes("m4a")) ext = "m4a";
        setAudioFile(new File([audioBlob], `recording.${ext}`, { type: mimeType }));
        setImageFile(null);
        setSelectedImage(null);
        setCropRegion(null);
        setExtractedName("");
        setExtractError(null);
        setMediaMode("audio");
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

  // ── Name Extraction ─────────────────────────────────────────────────

  const handleExtractName = useCallback(
    (onPopulate?: (name: string) => void) => {
      const populate = onPopulate || onNameExtracted;
      setExtractError(null);

      if (imageFile) {
        setExtracting(true);
        guestSearchApi
          .extractName(imageFile, cropRegion || undefined, modelId)
          .then((data) => {
            setExtractedName(data.extracted_name);
            populate?.(data.extracted_name);
          })
          .catch((e: unknown) => {
            const msg = e instanceof Error ? e.message : "Extraction failed";
            setExtractError(msg);
          })
          .finally(() => {
            setExtracting(false);
          });
      } else if (audioFile) {
        setExtracting(true);
        guestSearchApi
          .extractName(audioFile, undefined, modelId)
          .then((data) => {
            setExtractedName(data.extracted_name);
            populate?.(data.extracted_name);
          })
          .catch((e: unknown) => {
            const msg = e instanceof Error ? e.message : "Extraction failed";
            setExtractError(msg);
          })
          .finally(() => {
            setExtracting(false);
          });
      } else {
        setExtractError("Please upload an image or record audio first");
      }
    },
    [imageFile, audioFile, cropRegion, onNameExtracted, modelId],
  );

  // ── Clear All ───────────────────────────────────────────────────────

  const handleClear = useCallback(
    (onClear?: () => void) => {
      setExtractedName("");
      setExtractError(null);
      setSelectedImage(null);
      setImageFile(null);
      setRecordedAudio(null);
      setAudioFile(null);
      setCropRegion(null);
      setMediaMode("none");
      if (imageInputRef.current) imageInputRef.current.value = "";
      if (cameraInputRef.current) cameraInputRef.current.value = "";
      onClear?.();
    },
    [],
  );

  return {
    // State
    selectedImage,
    imageFile,
    recordedAudio,
    audioFile,
    isRecording,
    cropRegion,
    extractedName,
    extracting,
    extractError,
    mediaMode,
    // Handlers
    handleUploadPhoto,
    handleTakePhoto,
    handleImageChange,
    handleClearImage,
    handleSpeakName,
    handleStopRecording,
    handleExtractName,
    handleClear,
    // Refs
    imageInputRef,
    cameraInputRef,
  };
}