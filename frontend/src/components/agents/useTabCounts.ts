/* Story 2.8 T3.1 — aggregate KB/Tools/Integrations counts for tab badges.
 *
 * Reads the SAME query keys the tabs themselves use (`useKbDocuments`,
 * `useAgentTools`, `useIntegrations`) so counts stay consistent with tab
 * contents and update when a tab mutates + invalidates. Each field is
 * `undefined` while its query hasn't resolved yet, so the badge hides
 * instead of flashing "0" (AC #2).
 */

import { useAgentTools } from "../../hooks/useAgentTools";
import { useIntegrations } from "../../hooks/useIntegrations";
import { useKbDocuments } from "../../hooks/useKbDocuments";
import type { TabCounts } from "./agentBuilderTypes";

export function useTabCounts(agentId: string | undefined): TabCounts {
  const kb = useKbDocuments(agentId);
  const tools = useAgentTools(agentId);
  const integrations = useIntegrations(agentId);

  return {
    documents: kb.query.isSuccess ? kb.documents.length : undefined,
    tools: tools.query.isSuccess ? tools.tools.length : undefined,
    integrations: integrations.query.isSuccess ? integrations.integrations.length : undefined,
  };
}
