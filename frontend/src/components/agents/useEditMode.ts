/* View/edit toggle for the Agent Builder tabs (redesign).
 *
 * Each tab is read-only by default; the user clicks Edit to mutate, then
 * Save/Cancel. A brand-new Agent has no record to view, so its Identity tab
 * starts in edit mode.
 */

import { useState } from "react";

export interface EditMode {
  editing: boolean;
  startEdit: () => void;
  stopEdit: () => void;
}

export function useEditMode(startEditing: boolean): EditMode {
  const [editing, setEditing] = useState(startEditing);
  return {
    editing,
    startEdit: () => setEditing(true),
    stopEdit: () => setEditing(false),
  };
}
