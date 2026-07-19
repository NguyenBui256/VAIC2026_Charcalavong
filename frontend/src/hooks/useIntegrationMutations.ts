/* Shared pool — TanStack Query mutation hooks for tenant-level Integrations (CRUD + test). */

import {
  useMutation,
  useQueryClient,
  type UseMutationResult,
} from "@tanstack/react-query";
import {
  createIntegration,
  deleteIntegration,
  testIntegration,
  updateIntegration,
  type ApiIntegration,
  type CreateIntegrationInput,
  type IntegrationTestResult,
  type UpdateIntegrationInput,
} from "../lib/integrationsApi";

export interface UseIntegrationMutationsResult {
  create: UseMutationResult<ApiIntegration, Error, CreateIntegrationInput>;
  update: UseMutationResult<
    ApiIntegration,
    Error,
    { integrationId: string; patch: UpdateIntegrationInput }
  >;
  remove: UseMutationResult<{ id: string }, Error, string>;
  test: UseMutationResult<IntegrationTestResult, Error, string>;
}

export function useIntegrationMutations(): UseIntegrationMutationsResult {
  const queryClient = useQueryClient();
  const key = ["integrations"];

  const create = useMutation<ApiIntegration, Error, CreateIntegrationInput>({
    mutationFn: (input) => createIntegration(input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key }),
  });

  const update = useMutation<
    ApiIntegration,
    Error,
    { integrationId: string; patch: UpdateIntegrationInput }
  >({
    mutationFn: ({ integrationId, patch }) => updateIntegration(integrationId, patch),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key }),
  });

  const remove = useMutation<{ id: string }, Error, string>({
    mutationFn: (integrationId) => deleteIntegration(integrationId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key }),
  });

  const test = useMutation<IntegrationTestResult, Error, string>({
    mutationFn: (integrationId) => testIntegration(integrationId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key }),
  });

  return { create, update, remove, test };
}
