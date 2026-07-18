/* Chat target lists (agents/workflows) for the target selector.
 * Fetches real data via existing API layers; tolerant of failures
 * (e.g. dev-mode 401) — falls back to empty lists instead of throwing.
 */

import { useEffect, useState } from "react";
import { listAgents } from "./agentsApi";
import { listWorkflows } from "./workflowsApi";

export interface ChatTargetOption {
  id: string;
  name: string;
}

export function useChatTargets(): {
  agents: ChatTargetOption[];
  workflows: ChatTargetOption[];
  loading: boolean;
} {
  const [agents, setAgents] = useState<ChatTargetOption[]>([]);
  const [workflows, setWorkflows] = useState<ChatTargetOption[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    Promise.allSettled([listAgents(), listWorkflows()]).then(([a, w]) => {
      if (cancelled) return;
      setAgents(
        a.status === "fulfilled"
          ? a.value.map((x) => ({ id: x.id, name: x.name }))
          : [],
      );
      setWorkflows(
        w.status === "fulfilled"
          ? w.value.map((x) => ({ id: x.id, name: x.name }))
          : [],
      );
      setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return { agents, workflows, loading };
}
