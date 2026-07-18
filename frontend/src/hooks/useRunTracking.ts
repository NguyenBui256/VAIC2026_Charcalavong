/* 3C — Run tracking reads: run status (polled), immutable graph (once),
 * node executions + rollbacks (polled). Polling stops at a terminal run status.
 */
import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import {
  getRun,
  getRunGraph,
  listRunNodes,
  type GraphSnapshot,
  type Run,
  type RunNodesResponse,
} from "../lib/runsApi";
import { isTerminalRun } from "../lib/runStatusMeta";

const POLL_MS = 2000;

export function useRun(runId: string): UseQueryResult<Run, Error> {
  return useQuery<Run, Error>({
    queryKey: ["run", runId],
    queryFn: () => getRun(runId),
    enabled: Boolean(runId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && isTerminalRun(status) ? false : POLL_MS;
    },
  });
}

export function useRunGraph(runId: string): UseQueryResult<GraphSnapshot, Error> {
  return useQuery<GraphSnapshot, Error>({
    queryKey: ["runGraph", runId],
    queryFn: () => getRunGraph(runId),
    enabled: Boolean(runId),
    staleTime: Infinity,
  });
}

export function useRunNodes(
  runId: string,
  runStatus: string | undefined,
): UseQueryResult<RunNodesResponse, Error> {
  const terminal = runStatus ? isTerminalRun(runStatus) : false;
  return useQuery<RunNodesResponse, Error>({
    queryKey: ["runNodes", runId],
    queryFn: () => listRunNodes(runId),
    enabled: Boolean(runId),
    refetchInterval: terminal ? false : POLL_MS,
  });
}
