/* Story 3.1 — Constraints chip-list editor (AC6): optional list of
 * "must check X" statements. Add via Enter/button, remove via chip's
 * dismiss control. Plain controlled list of strings — no drag-reorder
 * (YAGNI, not in scope).
 */

import { useState, type KeyboardEvent } from "react";
import { Button } from "../ui";

export interface ConstraintsEditorProps {
  id: string;
  value: string[];
  onChange: (next: string[]) => void;
}

export default function ConstraintsEditor({ id, value, onChange }: ConstraintsEditorProps) {
  const [draft, setDraft] = useState("");

  function addConstraint() {
    const trimmed = draft.trim();
    if (!trimmed) return;
    onChange([...value, trimmed]);
    setDraft("");
  }

  function removeConstraint(index: number) {
    onChange(value.filter((_, i) => i !== index));
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      addConstraint();
    }
  }

  return (
    <div data-testid="vaic-constraints-editor">
      <div
        className="vaic-chip-list"
        style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-1)", marginBottom: "var(--space-2)" }}
      >
        {value.map((constraint, index) => (
          <span key={`${constraint}-${index}`} className="vaic-chip" data-testid="vaic-constraint-chip">
            {constraint}
            <button
              type="button"
              className="vaic-chip-remove vaic-focusable"
              aria-label={`Remove constraint: ${constraint}`}
              onClick={() => removeConstraint(index)}
            >
              &times;
            </button>
          </span>
        ))}
      </div>
      <div style={{ display: "flex", gap: "var(--space-2)" }}>
        <input
          id={id}
          className="vaic-form-input vaic-focusable"
          placeholder="e.g. must check credit score"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={handleKeyDown}
        />
        <Button variant="secondary" onClick={addConstraint} disabled={!draft.trim()}>
          Add
        </Button>
      </div>
    </div>
  );
}
