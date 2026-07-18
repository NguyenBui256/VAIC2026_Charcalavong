/* Shared pool — TanStack Query hook for the tenant-level Integrations list. */

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { listIntegrations, type ApiIntegration } from "../lib/integrationsApi";

export interface UseIntegrationsResult {
  query: UseQueryResult<ApiIntegration[], Error>;
  integrations: ApiIntegration[];
  isLoading: boolean;
  isError: boolean;
}

export function useIntegrations(): UseIntegrationsResult {
  const query = useQuery<ApiIntegration[], Error>({
    queryKey: ["integrations"],
    queryFn: listIntegrations,
  });

  return {
    query,
    integrations: query.data ?? [],
    isLoading: query.isLoading,
    isError: query.isError,
  };
}
