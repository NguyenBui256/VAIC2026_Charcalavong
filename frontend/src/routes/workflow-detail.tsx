/* Story 3.1 — Detail shell route (/workflows/:id), including the "new" flow. */

import { useParams } from "react-router-dom";
import WorkflowDetailShell from "../components/workflows/WorkflowDetailShell";

export default function WorkflowDetailPage() {
  const { id } = useParams<{ id: string }>();
  return <WorkflowDetailShell workflowId={id ?? "new"} />;
}
