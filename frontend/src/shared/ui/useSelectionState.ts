import { useState, useRef } from "react";

export interface UseSelectionStateOptions<TSelection, TData> {
  apiFetcher: (selection: TSelection) => Promise<TData>;
}

export interface SelectionState<TData> {
  data: TData | null;
  isLoading: boolean;
  error: string | null;
}

export default function useSelectionState<TSelection extends { prompt_id: string; version?: number }, TData>(
  selection: TSelection | null,
  options: UseSelectionStateOptions<TSelection, TData>
): SelectionState<TData> {
  const [data, setData] = useState<TData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Track the last fetched selection to prevent redundant API calls
  const lastFetchedRef = useRef<TSelection | null>(null);

  const { apiFetcher } = options;

  // Reset state when selection is null
  if (!selection) {
    lastFetchedRef.current = null;
    return { data: null, isLoading: false, error: null };
  }

  // Skip if this exact selection was already fetched
  const last = lastFetchedRef.current;
  if (
    last &&
    last.prompt_id === selection.prompt_id &&
    last.version === selection.version
  ) {
    return { data, isLoading: false, error };
  }

  // Update the ref with the new selection
  lastFetchedRef.current = selection;
  setIsLoading(true);
  setError(null);

  apiFetcher(selection)
    .then((result) => {
      // Only update if the selection hasn't changed since we started fetching
      const current = lastFetchedRef.current;
      if (
        current &&
        current.prompt_id === selection.prompt_id &&
        current.version === selection.version
      ) {
        setData(result);
      }
    })
    .catch((e) => {
      const current = lastFetchedRef.current;
      if (
        current &&
        current.prompt_id === selection.prompt_id &&
        current.version === selection.version
      ) {
        setError(e instanceof Error ? e.message : String(e));
      }
    })
    .finally(() => {
      const current = lastFetchedRef.current;
      if (
        current &&
        current.prompt_id === selection.prompt_id &&
        current.version === selection.version
      ) {
        setIsLoading(false);
      }
    });

  return { data, isLoading, error };
}