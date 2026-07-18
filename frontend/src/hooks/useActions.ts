import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createAction, deleteAction, listActions, listMiniAppDatabases, updateAction,
  type ActionBinding, type CreateActionInput, type MiniAppDatabaseOption, type UpdateActionInput,
} from "../lib/actionsApi";

const KEY = ["actions"] as const;

export function useActions() {
  return useQuery<ActionBinding[], Error>({ queryKey: KEY, queryFn: listActions });
}

export function useMiniAppDatabasesList() {
  return useQuery<MiniAppDatabaseOption[], Error>({
    queryKey: ["mini-app-databases", "options"],
    queryFn: listMiniAppDatabases,
  });
}

export function useActionMutations() {
  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: KEY });

  const create = useMutation<ActionBinding, Error, CreateActionInput>({
    mutationFn: createAction, onSuccess: invalidate,
  });
  const update = useMutation<ActionBinding, Error, { id: string; input: UpdateActionInput }>({
    mutationFn: ({ id, input }) => updateAction(id, input), onSuccess: invalidate,
  });
  const remove = useMutation<{ id: string }, Error, string>({
    mutationFn: deleteAction, onSuccess: invalidate,
  });
  return { create, update, remove };
}
