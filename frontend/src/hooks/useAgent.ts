/* Story 2.2 — TanStack Query hook for a single Agent (AC #5, #6, #7). */

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { getAgent, type Agent } from "../lib/agentsApi";

export interface UseAgentResult {
  query: UseQueryResult<Agent, Error>;
  isLoading: boolean;
  isError: boolean;
  data: Agent | undefined;
}

/** `id` is undefined (or "new") for the New Agent flow — the query is disabled. */
export function useAgent(id: string | undefined): UseAgentResult {
  const query = useQuery<Agent, Error>({
    queryKey: ["agent", id],
    queryFn: () => getAgent(id as string),
    enabled: Boolean(id) && id !== "new",
  });

  return {
    query,
    isLoading: query.isLoading,
    isError: query.isError,
    data: query.data,
  };
}
