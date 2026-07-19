/* 3C — Status pill for any run/node status. Reuses the app's StatusPill by
 * mapping the full backend vocabulary onto its 6 RunStates (runStatusMeta),
 * with the raw status as the visible label.
 */
import { StatusPill } from "../../ui";
import { runStateFor, statusLabel } from "../../../lib/runStatusMeta";

export default function RunStatusBadge({ status }: { status: string }) {
  return <StatusPill state={runStateFor(status)} label={statusLabel(status)} />;
}
