/* Story 2.2 — Model tab placeholder. Functionality arrives in Story 2.3. */

import { Card } from "../../ui";
import { semanticIcons, ICON_STROKE_WIDTH } from "../../../lib/icons";

export default function ModelTab() {
  const Icon = semanticIcons.Model;
  return (
    <Card
      title="Model"
      headerAction={<Icon size={18} strokeWidth={ICON_STROKE_WIDTH} style={{ color: "var(--color-text-tertiary)" }} aria-hidden="true" />}
    >
      <p className="text-body" style={{ color: "var(--color-text-tertiary)" }}>
        Coming soon — the provider picker arrives in Story 2.3.
      </p>
    </Card>
  );
}
