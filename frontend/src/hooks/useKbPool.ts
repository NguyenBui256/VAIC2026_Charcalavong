/* Shared pool — TanStack Query hooks for the tenant-level Knowledge Base pool.
 *
 * Polls while any document is still `processing` so Processing -> Indexed
 * / Failed is reflected without a manual refresh; stops polling once every
 * document has settled.
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from "@tanstack/react-query";
import {
  deleteKbDocument,
  listKbDocuments,
  uploadKbDocument,
  type KbDocument,
} from "../lib/kbApi";

const POLL_INTERVAL_MS = 2000;

export interface UseKbPoolResult {
  query: UseQueryResult<KbDocument[], Error>;
  documents: KbDocument[];
  isLoading: boolean;
  isError: boolean;
}

export function useKbPool(): UseKbPoolResult {
  const query = useQuery<KbDocument[], Error>({
    queryKey: ["kb-pool"],
    queryFn: listKbDocuments,
    refetchInterval: (q) => {
      const docs = q.state.data ?? [];
      return docs.some((d) => d.status === "processing") ? POLL_INTERVAL_MS : false;
    },
  });

  return {
    query,
    documents: query.data ?? [],
    isLoading: query.isLoading,
    isError: query.isError,
  };
}

export interface UseKbPoolMutationsResult {
  upload: UseMutationResult<KbDocument, Error, File>;
  remove: UseMutationResult<{ id: string }, Error, string>;
}

export function useKbPoolMutations(): UseKbPoolMutationsResult {
  const queryClient = useQueryClient();
  const key = ["kb-pool"];

  const upload = useMutation<KbDocument, Error, File>({
    mutationFn: (file) => uploadKbDocument(file),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key }),
  });

  const remove = useMutation<{ id: string }, Error, string>({
    mutationFn: (documentId) => deleteKbDocument(documentId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key }),
  });

  return { upload, remove };
}
