/* Story 3.1 — TanStack Query mutations for Workflow create/update. */

import { useMutation, useQueryClient, type UseMutationResult } from "@tanstack/react-query";
import {
  createWorkflow,
  updateWorkflow,
  type Workflow,
  type CreateWorkflowInput,
  type UpdateWorkflowInput,
} from "../lib/workflowsApi";

export interface UseWorkflowMutationsResult {
  update: UseMutationResult<Workflow, Error, UpdateWorkflowInput>;
  create: UseMutationResult<Workflow, Error, CreateWorkflowInput>;
}

/** `id` is the Workflow being edited (ignored by the create mutation). */
export function useWorkflowMutations(id: string | undefined): UseWorkflowMutationsResult {
  const queryClient = useQueryClient();

  const update = useMutation<Workflow, Error, UpdateWorkflowInput>({
    mutationFn: (patch) => updateWorkflow(id as string, patch),
    onSuccess: (workflow) => {
      queryClient.invalidateQueries({ queryKey: ["workflows"] });
      queryClient.setQueryData(["workflow", workflow.id], workflow);
    },
  });

  const create = useMutation<Workflow, Error, CreateWorkflowInput>({
    mutationFn: (input) => createWorkflow(input),
    onSuccess: (workflow) => {
      queryClient.invalidateQueries({ queryKey: ["workflows"] });
      queryClient.setQueryData(["workflow", workflow.id], workflow);
    },
  });

  return { update, create };
}
