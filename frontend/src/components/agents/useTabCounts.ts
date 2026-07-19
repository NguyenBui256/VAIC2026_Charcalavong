/* Story 2.8 T3.1 — aggregate KB/Tools counts for tab badges.
 *
 * Plan 2026-07-18 Task 8: counts now reflect GRANTED items (`useAgentGrants`),
 * not the tenant-wide pool — consistent with the tabs becoming grant pickers.
 * Each field is `undefined` while its query hasn't resolved yet, so the
 * badge hides instead of flashing "0" (AC #2).
 */

import { useAgentGrants } from "../../hooks/useAgentGrants";
import type { TabCounts } from "./agentBuilderTypes";

export function useTabCounts(agentId: string | undefined): TabCounts {
  const { toolsQuery, kbQuery, tools, kb } = useAgentGrants(agentId);

  return {
    documents: kbQuery.isSuccess ? kb.length : undefined,
    tools: toolsQuery.isSuccess ? tools.length : undefined,
  };
}
