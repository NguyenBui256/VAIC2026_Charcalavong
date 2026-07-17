/* Story 2.2 — TanStack Query hook for the Agent list (AC #1, #2, #3). */

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { listAgents, type Agent, type AgentListParams } from "../lib/agentsApi";

export interface UseAgentsResult {
  query: UseQueryResult<Agent[], Error>;
  isLoading: boolean;
  isError: boolean;
  data: Agent[] | undefined;
}

export function useAgents(params: AgentListParams): UseAgentsResult {
  const query = useQuery<Agent[], Error>({
    queryKey: ["agents", params],
    queryFn: () => listAgents(params),
  });

  return {
    query,
    isLoading: query.isLoading,
    isError: query.isError,
    data: query.data,
  };
}
