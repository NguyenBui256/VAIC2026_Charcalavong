/* 3D — load the authored graph for the editor. */

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { getWorkflowGraph, type GraphDefinition } from "../lib/workflowGraphApi";

export function useWorkflowGraph(
  workflowId: string | undefined,
): UseQueryResult<GraphDefinition, Error> {
  return useQuery<GraphDefinition, Error>({
    queryKey: ["workflowGraph", workflowId],
    queryFn: () => getWorkflowGraph(workflowId as string),
    enabled: Boolean(workflowId),
    staleTime: 30 * 1000,
  });
}
