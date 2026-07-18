import { apiFetch } from "./api";

export interface Notification {
  id: string;
  category: string;
  title: string;
  body: string;
  ref: Record<string, unknown>;
  read_at: string | null;
  created_at: string;
}

export const listNotifications = (unread = false) =>
  apiFetch<Notification[]>(`/notifications${unread ? "?unread=true" : ""}`);

export const markNotificationRead = (id: string) =>
  apiFetch<Notification>(`/notifications/${id}/read`, { method: "PATCH" });

export const markAllNotificationsRead = () =>
  apiFetch<{ updated: number }>(`/notifications/read-all`, { method: "POST" });
