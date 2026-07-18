import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { authHeaders } from "../../lib/api";
import type { AuditEvent } from "./types";

export type StreamState = "connecting" | "live" | "polling";

export function useAuditStream(sessionId: string, enabled: boolean, lastSequence: number) {
  const client = useQueryClient();
  const [state, setState] = useState<StreamState>("connecting");
  const sequence = useRef(lastSequence);

  useEffect(() => { sequence.current = Math.max(sequence.current, lastSequence); }, [lastSequence]);

  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    let pollTimer: ReturnType<typeof setInterval> | undefined;

    const refresh = () => {
      void client.invalidateQueries({ queryKey: ["audit-session", sessionId] });
      void client.invalidateQueries({ queryKey: ["audit-spans", sessionId] });
      void client.invalidateQueries({ queryKey: ["audit-events", sessionId] });
      void client.invalidateQueries({ queryKey: ["audit-graph", sessionId] });
    };

    async function connect() {
      try {
        const response = await fetch(`/api/audit/sessions/${sessionId}/stream?after=${sequence.current}`, {
          headers: { ...authHeaders(), Accept: "text/event-stream" },
          signal: controller.signal,
        });
        if (!response.ok || !response.body) throw new Error("stream unavailable");
        setState("live");
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        while (!controller.signal.aborted) {
          const { done, value } = await reader.read();
          if (done) throw new Error("stream closed");
          buffer += decoder.decode(value, { stream: true });
          const blocks = buffer.split("\n\n");
          buffer = blocks.pop() ?? "";
          for (const block of blocks) {
            const dataLine = block.split("\n").find((line) => line.startsWith("data: "));
            if (!dataLine) continue;
            const event = JSON.parse(dataLine.slice(6)) as AuditEvent;
            sequence.current = Math.max(sequence.current, event.sequence_no);
            refresh();
          }
        }
      } catch {
        if (controller.signal.aborted) return;
        setState("polling");
        refresh();
        pollTimer = setInterval(refresh, 2000);
      }
    }
    void connect();
    return () => {
      controller.abort();
      if (pollTimer) clearInterval(pollTimer);
    };
  }, [client, enabled, sessionId]);

  return state;
}
