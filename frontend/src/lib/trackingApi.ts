/* Tracking inbox API — typed wrappers around apiFetch for the per-user
 * cross-run review endpoints. apiFetch injects JWT + tenant and unwraps
 * the {data,error,meta} envelope.
 */
import { apiFetch } from "./api";

export interface TrackingNodeRef {
  node_key: string;
  label: string;
}

export interface TrackingCurrentNode {
  node_key: string;
  label: string;
  status: string;
}

export interface TrackingItem {
  run_id: string;
  workflow_id: string;
  workflow_name: string;
  run_status: string;
  my_awaiting_nodes: TrackingNodeRef[];
  current_node: TrackingCurrentNode | null;
  is_my_turn: boolean;
  updated_at: string | null;
}

export function getTracking(scope: "active" | "all"): Promise<TrackingItem[]> {
  return apiFetch<TrackingItem[]>(`/me/tracking?scope=${scope}`);
}

export function getTrackingSummary(): Promise<{ awaiting_my_review: number }> {
  return apiFetch<{ awaiting_my_review: number }>(`/me/tracking/summary`);
}
