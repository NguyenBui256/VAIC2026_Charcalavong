/* Story 3.1 — TanStack Query hook for the Workflow list (AC #3, #5). */

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { listWorkflows, type Workflow, type WorkflowListParams } from "../lib/workflowsApi";

export interface UseWorkflowsResult {
  query: UseQueryResult<Workflow[], Error>;
  isLoading: boolean;
  isError: boolean;
  data: Workflow[] | undefined;
}

export function useWorkflows(params: WorkflowListParams): UseWorkflowsResult {
  const query = useQuery<Workflow[], Error>({
    queryKey: ["workflows", params],
    queryFn: () => listWorkflows(params),
  });

  return {
    query,
    isLoading: query.isLoading,
    isError: query.isError,
    data: query.data,
  };
}
