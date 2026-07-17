/* Story 2.4 — TanStack Query hook for the KB document list (AC2).
 *
 * Polls while any document is still `processing` so Processing -> Indexed
 * / Failed is reflected without a manual refresh; stops polling once every
 * document has settled.
 */

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { listKbDocuments, type KbDocument } from "../lib/kbApi";

const POLL_INTERVAL_MS = 2000;

export interface UseKbDocumentsResult {
  query: UseQueryResult<KbDocument[], Error>;
  documents: KbDocument[];
  isLoading: boolean;
  isError: boolean;
}

export function useKbDocuments(agentId: string | undefined): UseKbDocumentsResult {
  const query = useQuery<KbDocument[], Error>({
    queryKey: ["kb", agentId],
    queryFn: () => listKbDocuments(agentId as string),
    enabled: Boolean(agentId) && agentId !== "new",
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
