/**
 * React Query hooks for LLM Models domain.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { LLMModel, CreateModelRequest, UpdateModelRequest, ModelInfoResponse, ModelsApiResponse } from '@/shared/types';
import { modelsApi, settingsApi } from '@/shared/api';

const MODELS_QUERY_KEY = ['models'] as const;

/** Fetch all LLM models */
export function useModels() {
  return useQuery<LLMModel[]>({
    queryKey: MODELS_QUERY_KEY,
    queryFn: () => modelsApi.getAll(),
  });
}

/** Fetch a single model by ID */
export function useModel(modelId: number) {
  return useQuery<LLMModel>({
    queryKey: [...MODELS_QUERY_KEY, modelId],
    queryFn: () => modelsApi.getById(modelId),
    enabled: !!modelId,
  });
}

/** Fetch all models via settings endpoint (legacy) */
export function useSettingsModels() {
  return useQuery<ModelsApiResponse>({
    queryKey: [...MODELS_QUERY_KEY, 'settings'],
    queryFn: () => settingsApi.getModels(),
  });
}

/** Create a new model */
export function useCreateModel() {
  const queryClient = useQueryClient();

  return useMutation<LLMModel, Error, CreateModelRequest>({
    mutationFn: (payload) => modelsApi.create(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: MODELS_QUERY_KEY });
    },
  });
}

/** Update an existing model */
export function useUpdateModel() {
  const queryClient = useQueryClient();

  return useMutation<LLMModel, Error, { modelId: number; payload: UpdateModelRequest }>({
    mutationFn: ({ modelId, payload }) => modelsApi.update(modelId, payload),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: MODELS_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: [...MODELS_QUERY_KEY, variables.modelId] });
    },
  });
}

/** Delete a model */
export function useDeleteModel() {
  const queryClient = useQueryClient();

  return useMutation<{ ok: boolean }, Error, number>({
    mutationFn: (modelId) => modelsApi.delete(modelId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: MODELS_QUERY_KEY });
    },
  });
}

/** Fetch model info from external Ollama endpoint */
export function useFetchModelInfo() {
  const queryClient = useQueryClient();

  return useMutation<ModelInfoResponse, Error, string>({
    mutationFn: (modelsEndpoint) => modelsApi.fetchInfo(modelsEndpoint),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: MODELS_QUERY_KEY });
    },
  });
}