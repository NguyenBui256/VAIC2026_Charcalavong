/* 3D — persist the whole graph (PUT); invalidate graph + workflow (version++). */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { putWorkflowGraph, type GraphDefinition } from "../lib/workflowGraphApi";

export function useWorkflowGraphMutation(workflowId: string) {
  const queryClient = useQueryClient();
  const mutation = useMutation<GraphDefinition, Error, GraphDefinition>({
    mutationFn: (def) => putWorkflowGraph(workflowId, def),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workflowGraph", workflowId] });
      queryClient.invalidateQueries({ queryKey: ["workflow", workflowId] });
    },
  });
  return { mutateAsync: mutation.mutateAsync, isPending: mutation.isPending };
}
