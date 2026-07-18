/* Shared pool — TanStack Query hooks for per-agent grants (Tools + KB documents).
 *
 * Wraps `agentGrantsApi`: lists what an agent has been granted from the
 * shared pool, plus attach/detach mutations that invalidate the relevant
 * grant list.
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from "@tanstack/react-query";
import {
  attachAgentKb,
  attachAgentTool,
  detachAgentKb,
  detachAgentTool,
  listAgentKb,
  listAgentTools,
} from "../lib/agentGrantsApi";
import type { Tool } from "../lib/toolsApi";
import type { KbDocument } from "../lib/kbApi";

export interface UseAgentGrantsResult {
  toolsQuery: UseQueryResult<Tool[], Error>;
  kbQuery: UseQueryResult<KbDocument[], Error>;
  tools: Tool[];
  kb: KbDocument[];
  isLoading: boolean;
  isError: boolean;
  attachTool: UseMutationResult<unknown, Error, string>;
  detachTool: UseMutationResult<unknown, Error, string>;
  attachKb: UseMutationResult<unknown, Error, string>;
  detachKb: UseMutationResult<unknown, Error, string>;
}

export function useAgentGrants(agentId: string | undefined): UseAgentGrantsResult {
  const queryClient = useQueryClient();
  const enabled = Boolean(agentId) && agentId !== "new";
  const toolsKey = ["agent-tools", agentId];
  const kbKey = ["agent-kb", agentId];

  const toolsQuery = useQuery<Tool[], Error>({
    queryKey: toolsKey,
    queryFn: () => listAgentTools(agentId as string),
    enabled,
  });

  const kbQuery = useQuery<KbDocument[], Error>({
    queryKey: kbKey,
    queryFn: () => listAgentKb(agentId as string),
    enabled,
  });

  const attachTool = useMutation<unknown, Error, string>({
    mutationFn: (toolId) => attachAgentTool(agentId as string, toolId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: toolsKey }),
  });

  const detachTool = useMutation<unknown, Error, string>({
    mutationFn: (toolId) => detachAgentTool(agentId as string, toolId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: toolsKey }),
  });

  const attachKb = useMutation<unknown, Error, string>({
    mutationFn: (docId) => attachAgentKb(agentId as string, docId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: kbKey }),
  });

  const detachKb = useMutation<unknown, Error, string>({
    mutationFn: (docId) => detachAgentKb(agentId as string, docId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: kbKey }),
  });

  return {
    toolsQuery,
    kbQuery,
    tools: toolsQuery.data ?? [],
    kb: kbQuery.data ?? [],
    isLoading: toolsQuery.isLoading || kbQuery.isLoading,
    isError: toolsQuery.isError || kbQuery.isError,
    attachTool,
    detachTool,
    attachKb,
    detachKb,
  };
}
