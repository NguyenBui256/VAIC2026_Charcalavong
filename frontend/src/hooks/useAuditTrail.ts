/* Epic 6 (FR-22) — TanStack Query hook for the Trace Dashboard audit trail. */

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import {
  listAuditEntries,
  type AuditEntry,
  type AuditListParams,
} from "../lib/auditApi";

export function useAuditTrail(
  params: AuditListParams,
): UseQueryResult<AuditEntry[], Error> {
  return useQuery<AuditEntry[], Error>({
    queryKey: ["audit-trail", params],
    queryFn: () => listAuditEntries(params),
  });
}
