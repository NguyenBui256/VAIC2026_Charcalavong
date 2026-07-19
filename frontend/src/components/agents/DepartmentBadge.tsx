/* Story 2.2 — Department badge shown in the Agent list Department column. */

import { semanticIcons, ICON_STROKE_WIDTH } from "../../lib/icons";

export interface DepartmentBadgeProps {
  name: string;
}

export default function DepartmentBadge({ name }: DepartmentBadgeProps) {
  const Icon = semanticIcons.Department;
  return (
    <span className="vaic-dept-badge" data-testid="vaic-department-badge">
      <Icon size={12} strokeWidth={ICON_STROKE_WIDTH} aria-hidden="true" />
      <span>{name}</span>
    </span>
  );
}
