/* Story 2.4 — TanStack Query mutations for KB upload/delete (AC1, AC5). */

import { useMutation, useQueryClient, type UseMutationResult } from "@tanstack/react-query";
import { deleteKbDocument, uploadKbDocument, type KbDocument } from "../lib/kbApi";

export interface UseKbMutationsResult {
  upload: UseMutationResult<KbDocument, Error, File>;
  remove: UseMutationResult<{ id: string }, Error, string>;
}

export function useKbMutations(agentId: string | undefined): UseKbMutationsResult {
  const queryClient = useQueryClient();
  const key = ["kb", agentId];

  const upload = useMutation<KbDocument, Error, File>({
    mutationFn: (file) => uploadKbDocument(agentId as string, file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: key });
    },
  });

  const remove = useMutation<{ id: string }, Error, string>({
    mutationFn: (documentId) => deleteKbDocument(agentId as string, documentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: key });
    },
  });

  return { upload, remove };
}
