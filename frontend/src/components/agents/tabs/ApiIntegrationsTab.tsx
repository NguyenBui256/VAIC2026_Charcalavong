/* Story 2.2 — API Integrations tab placeholder. Functionality arrives in a later Epic 2 story. */

import { Card } from "../../ui";
import { semanticIcons, ICON_STROKE_WIDTH } from "../../../lib/icons";

export default function ApiIntegrationsTab() {
  const Icon = semanticIcons.ApiIntegration;
  return (
    <Card
      title="API Integrations"
      headerAction={<Icon size={18} strokeWidth={ICON_STROKE_WIDTH} style={{ color: "var(--color-text-tertiary)" }} aria-hidden="true" />}
    >
      <p className="text-body" style={{ color: "var(--color-text-tertiary)" }}>
        Coming soon — API Integrations arrive in a later Epic 2 story.
      </p>
    </Card>
  );
}
