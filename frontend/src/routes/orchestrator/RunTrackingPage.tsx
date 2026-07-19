/* 3C — route page for /workflows/:id/runs/:runId. */
import { useNavigate, useParams } from "react-router-dom";
import { Button } from "../../components/ui";
import RunTrackingView from "../../components/workflows/runs/RunTrackingView";

export default function RunTrackingPage() {
  const { id, runId } = useParams();
  const navigate = useNavigate();
  if (!runId) return null;
  return (
    <div data-testid="vaic-run-tracking-page">
      <Button variant="ghost" onClick={() => navigate(`/workflows/${id}`)}>
        Back to Workflow
      </Button>
      <RunTrackingView runId={runId} />
    </div>
  );
}
