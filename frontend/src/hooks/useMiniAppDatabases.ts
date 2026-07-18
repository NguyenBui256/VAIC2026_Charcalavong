import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createDatabase, deleteDatabase, listDatabaseRows, listDatabases, updateDatabase,
  type CreateDatabaseInput, type MiniAppDatabase, type MiniAppDatabaseRow, type UpdateDatabaseInput,
} from "../lib/miniAppDatabasesApi";

const KEY = ["mini-app-databases"] as const;

export function useMiniAppDatabases() {
  return useQuery<MiniAppDatabase[], Error>({ queryKey: KEY, queryFn: listDatabases });
}

export function useMiniAppDatabaseRows(id: string | undefined) {
  return useQuery<MiniAppDatabaseRow[], Error>({
    queryKey: [...KEY, id, "rows"],
    queryFn: () => listDatabaseRows(id as string),
    enabled: Boolean(id),
  });
}

export function useMiniAppDatabaseMutations() {
  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: KEY });

  const create = useMutation<MiniAppDatabase, Error, CreateDatabaseInput>({
    mutationFn: createDatabase, onSuccess: invalidate,
  });
  const update = useMutation<MiniAppDatabase, Error, { id: string; input: UpdateDatabaseInput }>({
    mutationFn: ({ id, input }) => updateDatabase(id, input), onSuccess: invalidate,
  });
  const remove = useMutation<{ id: string }, Error, string>({
    mutationFn: deleteDatabase, onSuccess: invalidate,
  });
  return { create, update, remove };
}
