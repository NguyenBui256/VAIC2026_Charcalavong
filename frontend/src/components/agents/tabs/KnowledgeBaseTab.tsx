/* Story 2.2 — Knowledge Base tab placeholder. Functionality arrives in Story 2.4/2.5. */

import { Card } from "../../ui";
import { semanticIcons, ICON_STROKE_WIDTH } from "../../../lib/icons";

export default function KnowledgeBaseTab() {
  const Icon = semanticIcons.KnowledgeBase;
  return (
    <Card
      title="Knowledge Base"
      headerAction={<Icon size={18} strokeWidth={ICON_STROKE_WIDTH} style={{ color: "var(--color-text-tertiary)" }} aria-hidden="true" />}
    >
      <p className="text-body" style={{ color: "var(--color-text-tertiary)" }}>
        Coming soon — Knowledge Base upload and retrieval arrive in Story 2.4/2.5.
      </p>
    </Card>
  );
}
