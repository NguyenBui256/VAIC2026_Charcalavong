/* Story 2.2 — Detail shell route (/agents/:id), including the "new" flow. */

import { useParams } from "react-router-dom";
import AgentDetailShell from "../components/agents/AgentDetailShell";

export default function AgentDetailPage() {
  const { id } = useParams<{ id: string }>();
  return <AgentDetailShell agentId={id ?? "new"} />;
}
