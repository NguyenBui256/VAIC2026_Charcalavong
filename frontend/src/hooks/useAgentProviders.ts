/* Story 2.3 T4.1 — TanStack Query hook for the runtime provider/model catalog. */

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { listProviders, type ProviderCatalogEntry } from "../lib/agentsApi";

export interface UseAgentProvidersResult {
  query: UseQueryResult<ProviderCatalogEntry[], Error>;
  isLoading: boolean;
  isError: boolean;
  data: ProviderCatalogEntry[] | undefined;
}

export function useAgentProviders(): UseAgentProvidersResult {
  const query = useQuery<ProviderCatalogEntry[], Error>({
    queryKey: ["agent-providers"],
    queryFn: listProviders,
    staleTime: 5 * 60 * 1000,
  });

  return {
    query,
    isLoading: query.isLoading,
    isError: query.isError,
    data: query.data,
  };
}
