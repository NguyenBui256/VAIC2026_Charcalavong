/* Story 2.6 — TanStack Query hooks for the Tools tab (list + CRUD + test). */

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
  listTools,
  testTool,
  updateTool,
  type CreateToolInput,
  type Tool,
  type ToolTestResult,
  type UpdateToolInput,
} from "../lib/toolsApi";

export interface UseAgentToolsResult {
  query: UseQueryResult<Tool[], Error>;
  tools: Tool[];
  isLoading: boolean;
  isError: boolean;
}

export function useAgentTools(agentId: string | undefined): UseAgentToolsResult {
  const query = useQuery<Tool[], Error>({
    queryKey: ["agent-tools", agentId],
    queryFn: () => listTools(agentId as string),
    enabled: Boolean(agentId) && agentId !== "new",
  });

  return {
    query,
    tools: query.data ?? [],
    isLoading: query.isLoading,
    isError: query.isError,
  };
}

export interface UseAgentToolMutationsResult {
  create: UseMutationResult<Tool, Error, CreateToolInput>;
  update: UseMutationResult<Tool, Error, { toolId: string; patch: UpdateToolInput }>;
  remove: UseMutationResult<{ id: string }, Error, string>;
  test: UseMutationResult<ToolTestResult, Error, { toolId: string; sampleInput: Record<string, unknown> }>;
}

export function useAgentToolMutations(agentId: string | undefined): UseAgentToolMutationsResult {
  const queryClient = useQueryClient();
  const key = ["agent-tools", agentId];

  const create = useMutation<Tool, Error, CreateToolInput>({
    mutationFn: (input) => createTool(agentId as string, input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key }),
  });

  const update = useMutation<Tool, Error, { toolId: string; patch: UpdateToolInput }>({
    mutationFn: ({ toolId, patch }) => updateTool(agentId as string, toolId, patch),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key }),
  });

  const remove = useMutation<{ id: string }, Error, string>({
    mutationFn: (toolId) => deleteTool(agentId as string, toolId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key }),
  });

  const test = useMutation<
    ToolTestResult,
    Error,
    { toolId: string; sampleInput: Record<string, unknown> }
  >({
    mutationFn: ({ toolId, sampleInput }) => testTool(agentId as string, toolId, sampleInput),
  });

  return { create, update, remove, test };
}
