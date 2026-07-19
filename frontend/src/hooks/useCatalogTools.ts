/* Shared pool — TanStack Query hooks for the tenant-level Tool catalog (list + CRUD + test). */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from "@tanstack/react-query";
import {
  createTool,
  deleteTool,
  listCatalogTools,
  testTool,
  updateTool,
  type CreateToolInput,
  type Tool,
  type ToolTestResult,
  type UpdateToolInput,
} from "../lib/toolsApi";

export interface UseCatalogToolsResult {
  query: UseQueryResult<Tool[], Error>;
  tools: Tool[];
  isLoading: boolean;
  isError: boolean;
}

export function useCatalogTools(): UseCatalogToolsResult {
  const query = useQuery<Tool[], Error>({
    queryKey: ["catalog-tools"],
    queryFn: listCatalogTools,
  });

  return {
    query,
    tools: query.data ?? [],
    isLoading: query.isLoading,
    isError: query.isError,
  };
}

export interface UseCatalogToolMutationsResult {
  create: UseMutationResult<Tool, Error, CreateToolInput>;
  update: UseMutationResult<Tool, Error, { toolId: string; patch: UpdateToolInput }>;
  remove: UseMutationResult<{ id: string }, Error, string>;
  test: UseMutationResult<ToolTestResult, Error, { toolId: string; sampleInput: Record<string, unknown> }>;
}

export function useCatalogToolMutations(): UseCatalogToolMutationsResult {
  const queryClient = useQueryClient();
  const key = ["catalog-tools"];

  const create = useMutation<Tool, Error, CreateToolInput>({
    mutationFn: (input) => createTool(input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key }),
  });

  const update = useMutation<Tool, Error, { toolId: string; patch: UpdateToolInput }>({
    mutationFn: ({ toolId, patch }) => updateTool(toolId, patch),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key }),
  });

  const remove = useMutation<{ id: string }, Error, string>({
    mutationFn: (toolId) => deleteTool(toolId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key }),
  });

  const test = useMutation<
    ToolTestResult,
    Error,
    { toolId: string; sampleInput: Record<string, unknown> }
  >({
    mutationFn: ({ toolId, sampleInput }) => testTool(toolId, sampleInput),
  });

  return { create, update, remove, test };
}
