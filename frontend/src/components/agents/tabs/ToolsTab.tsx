/* Story 2.2 — Tools tab placeholder. Functionality arrives in Story 2.6. */

import { Card } from "../../ui";
import { semanticIcons, ICON_STROKE_WIDTH } from "../../../lib/icons";

export default function ToolsTab() {
  const Icon = semanticIcons.Tool;
  return (
    <Card
      title="Tools"
      headerAction={<Icon size={18} strokeWidth={ICON_STROKE_WIDTH} style={{ color: "var(--color-text-tertiary)" }} aria-hidden="true" />}
    >
      <p className="text-body" style={{ color: "var(--color-text-tertiary)" }}>
        Coming soon — Tool schemas arrive in Story 2.6.
      </p>
    </Card>
  );
}
