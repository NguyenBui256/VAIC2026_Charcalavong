/* Story 3.1 — TanStack Query hook for a single Workflow (AC #6). */

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { getWorkflow, type Workflow } from "../lib/workflowsApi";

export interface UseWorkflowResult {
  query: UseQueryResult<Workflow, Error>;
  isLoading: boolean;
  isError: boolean;
  data: Workflow | undefined;
}

/** `id` is undefined (or "new") for the New Workflow flow — the query is disabled. */
export function useWorkflow(id: string | undefined): UseWorkflowResult {
  const query = useQuery<Workflow, Error>({
    queryKey: ["workflow", id],
    queryFn: () => getWorkflow(id as string),
    enabled: Boolean(id) && id !== "new",
  });

  return {
    query,
    isLoading: query.isLoading,
    isError: query.isError,
    data: query.data,
  };
}
