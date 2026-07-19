/* Story 2.2 — TanStack Query hook for the Department list (filter + Identity select). */

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { listDepartments, type Department } from "../lib/departmentsApi";

export interface UseDepartmentsResult {
  query: UseQueryResult<Department[], Error>;
  isLoading: boolean;
  isError: boolean;
  data: Department[] | undefined;
}

export function useDepartments(): UseDepartmentsResult {
  const query = useQuery<Department[], Error>({
    queryKey: ["departments"],
    queryFn: listDepartments,
  });

  return {
    query,
    isLoading: query.isLoading,
    isError: query.isError,
    data: query.data,
  };
}
