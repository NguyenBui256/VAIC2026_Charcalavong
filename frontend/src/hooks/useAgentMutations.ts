/* Story 2.2 — TanStack Query mutations for Agent create/update (AC #9). */

import { useMutation, useQueryClient, type UseMutationResult } from "@tanstack/react-query";
import {
  createAgent,
  updateAgent,
  type Agent,
  type CreateAgentInput,
  type UpdateAgentInput,
} from "../lib/agentsApi";

export interface UseAgentMutationsResult {
  update: UseMutationResult<Agent, Error, UpdateAgentInput>;
  create: UseMutationResult<Agent, Error, CreateAgentInput>;
}

/** `id` is the Agent being edited (ignored by the create mutation). */
export function useAgentMutations(id: string | undefined): UseAgentMutationsResult {
  const queryClient = useQueryClient();

  const update = useMutation<Agent, Error, UpdateAgentInput>({
    mutationFn: (patch) => updateAgent(id as string, patch),
    onSuccess: (agent) => {
      queryClient.invalidateQueries({ queryKey: ["agents"] });
      queryClient.setQueryData(["agent", agent.id], agent);
    },
  });

  const create = useMutation<Agent, Error, CreateAgentInput>({
    mutationFn: (input) => createAgent(input),
    onSuccess: (agent) => {
      queryClient.invalidateQueries({ queryKey: ["agents"] });
      queryClient.setQueryData(["agent", agent.id], agent);
    },
  });

  return { update, create };
}
