/* Tracking inbox reads — both polled at 3s. The list drives the Tracking
 * page; the summary drives the Sidebar badge (kept as a separate light query
 * so the badge does not pull the whole list).
 */
import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import {
  getTracking,
  getTrackingSummary,
  type TrackingItem,
} from "../lib/trackingApi";

const POLL_MS = 3000;

export function useTrackingList(
  scope: "active" | "all",
): UseQueryResult<TrackingItem[], Error> {
  return useQuery<TrackingItem[], Error>({
    queryKey: ["tracking", scope],
    queryFn: () => getTracking(scope),
    refetchInterval: POLL_MS,
  });
}

export function useTrackingSummary(): UseQueryResult<
  { awaiting_my_review: number },
  Error
> {
  return useQuery<{ awaiting_my_review: number }, Error>({
    queryKey: ["trackingSummary"],
    queryFn: () => getTrackingSummary(),
    refetchInterval: POLL_MS,
  });
}
