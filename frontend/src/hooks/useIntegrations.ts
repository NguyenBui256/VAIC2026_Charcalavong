/* Story 2.7 — TanStack Query hook for the API Integrations tab list. */

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { listIntegrations, type ApiIntegration } from "../lib/integrationsApi";

export interface UseIntegrationsResult {
  query: UseQueryResult<ApiIntegration[], Error>;
  integrations: ApiIntegration[];
  isLoading: boolean;
  isError: boolean;
}

export function useIntegrations(agentId: string | undefined): UseIntegrationsResult {
  const query = useQuery<ApiIntegration[], Error>({
    queryKey: ["integrations", agentId],
    queryFn: () => listIntegrations(agentId as string),
    enabled: Boolean(agentId) && agentId !== "new",
  });

  return {
    query,
    integrations: query.data ?? [],
    isLoading: query.isLoading,
    isError: query.isError,
  };
}
