/* 3C — Runs list for a Workflow (Runs tab). */
import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { listRuns, type Run } from "../lib/runsApi";

export function useRuns(workflowId: string): UseQueryResult<Run[], Error> {
  return useQuery<Run[], Error>({
    queryKey: ["runs", workflowId],
    queryFn: () => listRuns(workflowId),
    enabled: Boolean(workflowId),
  });
}
