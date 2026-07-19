import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  listNotifications, markAllNotificationsRead, markNotificationRead,
  type Notification,
} from "../lib/notificationsApi";

const KEY = ["notifications"] as const;
const POLL_INTERVAL_MS = 10_000;

export function useNotifications() {
  return useQuery<Notification[], Error>({
    queryKey: KEY,
    queryFn: () => listNotifications(false),
    refetchInterval: POLL_INTERVAL_MS,
  });
}

export function useNotificationMutations() {
  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: KEY });

  const markRead = useMutation<Notification, Error, string>({
    mutationFn: markNotificationRead, onSuccess: invalidate,
  });
  const markAllRead = useMutation<{ updated: number }, Error, void>({
    mutationFn: markAllNotificationsRead, onSuccess: invalidate,
  });
  return { markRead, markAllRead };
}
