/* Shared view/edit action controls for the Agent Builder tabs (redesign).
 *
 *  • FieldEditActions — footer for form tabs (Identity/Prompt/Model):
 *    "Edit" while viewing; "Save" + "Cancel" while editing. A new Agent has
 *    no view state, so it shows "Create Agent" + "Cancel" instead.
 *  • ListEditActions — footer for collection tabs (Knowledge Base/Tools/API
 *    Integrations): "Edit" while viewing; "Done" + the create CTA while editing.
 *    Same bottom-right position as FieldEditActions for a consistent layout.
 */

import type { ReactNode } from "react";
import { Pencil } from "lucide-react";
import { Button } from "../ui";
import { ICON_STROKE_WIDTH } from "../../lib/icons";

export interface FieldEditActionsProps {
  editing: boolean;
  isNew: boolean;
  onEdit: () => void;
  onSave: () => void;
  onCancel: () => void;
  saving?: boolean;
  /** Disable Save when the form is incomplete (e.g. Model needs provider). */
  canSave?: boolean;
}

export function FieldEditActions({
  editing,
  isNew,
  onEdit,
  onSave,
  onCancel,
  saving = false,
  canSave = true,
}: FieldEditActionsProps) {
  if (!editing && !isNew) {
    return (
      <div className="vaic-form-footer">
        <Button
          variant="secondary"
          onClick={onEdit}
          icon={<Pencil size={16} strokeWidth={ICON_STROKE_WIDTH} aria-hidden="true" />}
          data-testid="vaic-tab-edit"
        >
          Edit
        </Button>
      </div>
    );
  }

  return (
    <div className="vaic-form-footer">
      <Button variant="ghost" onClick={onCancel} disabled={saving} data-testid="vaic-tab-cancel">
        Cancel
      </Button>
      <Button
        variant="primary"
        onClick={onSave}
        disabled={saving || !canSave}
        data-testid="vaic-tab-save"
      >
        {isNew ? "Create Agent" : "Save"}
      </Button>
    </div>
  );
}

export interface ListEditActionsProps {
  editing: boolean;
  onEdit: () => void;
  onDone: () => void;
  /** Primary create CTA (New/Upload) rendered on the right while editing. */
  children?: ReactNode;
}

/* Footer for collection tabs — same bottom-right position as FieldEditActions
 * so every tab's edit controls live in one predictable place. */
export function ListEditActions({ editing, onEdit, onDone, children }: ListEditActionsProps) {
  if (!editing) {
    return (
      <div className="vaic-form-footer">
        <Button
          variant="secondary"
          onClick={onEdit}
          icon={<Pencil size={16} strokeWidth={ICON_STROKE_WIDTH} aria-hidden="true" />}
          data-testid="vaic-tab-edit"
        >
          Edit
        </Button>
      </div>
    );
  }
  return (
    <div className="vaic-form-footer">
      <Button variant="secondary" onClick={onDone} data-testid="vaic-tab-done">
        Done
      </Button>
      {children}
    </div>
  );
}
