/* 3D — tenant users query (long staleTime; the roster changes rarely). */

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { listUsers, type TenantUser } from "../lib/usersApi";

export function useUsers(): UseQueryResult<TenantUser[], Error> {
  return useQuery<TenantUser[], Error>({
    queryKey: ["users"],
    queryFn: listUsers,
    staleTime: 5 * 60 * 1000,
  });
}
