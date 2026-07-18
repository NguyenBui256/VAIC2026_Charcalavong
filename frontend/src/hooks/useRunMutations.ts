/* 3C — Node decision + rollback confirm mutations. Each invalidates the
 * run + node queries so the polled canvas reflects the new engine state
 * (the backend endpoint already re-enqueues run_workflow(resume=True)).
 */
import {
  useMutation,
  useQueryClient,
  type UseMutationResult,
} from "@tanstack/react-query";
import {
  confirmRollback,
  postDecision,
  type DecisionRequest,
  type RunNodeExecution,
} from "../lib/runsApi";

export interface UseRunMutationsResult {
  decide: UseMutationResult<
    RunNodeExecution,
    Error,
    { nodeKey: string; body: DecisionRequest }
  >;
  confirm: UseMutationResult<
    { id: string; status: string },
    Error,
    { rollbackId: string; accept: boolean; reason?: string }
  >;
}

export function useRunMutations(runId: string): UseRunMutationsResult {
  const queryClient = useQueryClient();
  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["runNodes", runId] });
    queryClient.invalidateQueries({ queryKey: ["run", runId] });
  };

  const decide = useMutation<
    RunNodeExecution,
    Error,
    { nodeKey: string; body: DecisionRequest }
  >({
    mutationFn: ({ nodeKey, body }) => postDecision(runId, nodeKey, body),
    onSuccess: invalidate,
  });

  const confirm = useMutation<
    { id: string; status: string },
    Error,
    { rollbackId: string; accept: boolean; reason?: string }
  >({
    mutationFn: ({ rollbackId, accept, reason }) =>
      confirmRollback(runId, rollbackId, accept, reason),
    onSuccess: invalidate,
  });

  return { decide, confirm };
}
