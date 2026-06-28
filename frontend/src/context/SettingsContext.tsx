import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { settingsApi } from "../services/api";
import type { AppSettings } from "../types";

interface SettingsContextValue {
  modelsEndpoint: string;
  modelName: string;
  vllmVersion: string;
  thinkingEnabled: boolean;
  expectedFormat: string;
  loading: boolean;
  saveSettings: (settings: AppSettings) => Promise<void>;
  refreshSettings: () => Promise<void>;
}

const SettingsContext = createContext<SettingsContextValue | null>(null);

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [modelsEndpoint, setModelsEndpoint] = useState("");
  const [modelName, setModelName] = useState("");
  const [vllmVersion, setVllmVersion] = useState("");
  const [thinkingEnabled, setThinkingEnabled] = useState(false);
  const [expectedFormat, setExpectedFormat] = useState("auto");
  const [loading, setLoading] = useState(true);

  const loadFromApi = async () => {
    try {
      const data = await settingsApi.get();
      const ts = data.test_settings;
      if (ts) {
        setModelsEndpoint(ts.models_endpoint ?? "");
        setModelName(ts.model_name ?? "");
        setVllmVersion(ts.vllm_version ?? "");
        setThinkingEnabled(ts.thinking_enabled ?? false);
        setExpectedFormat(ts.expected_format ?? "auto");
      }
    } finally {
      setLoading(false);
    }
  };

  // Load settings once on mount
  useEffect(() => {
    loadFromApi();
  }, []);

  const saveSettings = async (settings: AppSettings) => {
    try {
      await settingsApi.update(settings);
      // Update local state immediately after successful save
      const ts = settings.test_settings;
      if (ts) {
        setModelsEndpoint(ts.models_endpoint ?? "");
        setModelName(ts.model_name ?? "");
        setVllmVersion(ts.vllm_version ?? "");
        setThinkingEnabled(ts.thinking_enabled ?? false);
        setExpectedFormat(ts.expected_format ?? "auto");
      }
    } catch (err) {
      throw err;
    }
  };

  const refreshSettings = loadFromApi;

  return (
    <SettingsContext.Provider
      value={{
        modelsEndpoint,
        modelName,
        vllmVersion,
        thinkingEnabled,
        expectedFormat,
        loading,
        saveSettings,
        refreshSettings,
      }}
    >
      {children}
    </SettingsContext.Provider>
  );
}

export function useSettings() {
  const ctx = useContext(SettingsContext);
  if (!ctx) throw new Error("useSettings must be used within SettingsProvider");
  return ctx;
}