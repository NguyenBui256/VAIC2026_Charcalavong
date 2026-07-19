/* Story 2.2 — Identity tab (AC #7, #8, #9, #10).
 *
 * Form: Name (text, required), Department (select, required), System Prompt
 * (textarea, required), Status (Draft/Active toggle). Required fields show
 * `*` in destructive color; validation runs on blur (never keystroke) and is
 * also (re-)run on Save so a never-blurred empty field still surfaces its
 * error. All three fields share one local FieldWrapper that reproduces the
 * FormField (UX-DR8) visuals exactly (same CSS classes) — FormField itself
 * isn't used because its touched/error state is wired only to its own
 * default `<input>`, so a parent can't force-display validation on Save nor
 * drive a `<select>`/`<textarea>` through its `children` slot.
 */

import { useEffect, useState, type ReactNode } from "react";
import { useToast } from "../ui";
import { useDepartments } from "../../hooks/useDepartments";
import { useAgentMutations } from "../../hooks/useAgentMutations";
import { useRegisterTab } from "./AgentBuilderContext";
import { useEditMode } from "./useEditMode";
import { FieldEditActions } from "./TabEditBar";
import type { Agent, AgentStatus } from "../../lib/agentsApi";

export interface IdentityTabProps {
  agentId: string;
  isNew: boolean;
  agent: Agent | undefined;
  onDirtyChange: (dirty: boolean) => void;
  onSaved?: (agent: Agent) => void;
  /** New-Agent flow: Cancel discards and returns to the Agents list. */
  onCancelNew?: () => void;
}

interface FormState {
  name: string;
  departmentId: string;
  systemPrompt: string;
  status: AgentStatus;
}

function toFormState(agent: Agent | undefined): FormState {
  return {
    name: agent?.name ?? "",
    departmentId: agent?.department_id ?? "",
    systemPrompt: agent?.system_prompt ?? "",
    status: agent?.status ?? "draft",
  };
}

function validateRequired(value: string, label: string): string | null {
  return value.trim() ? null : `${label} is required`;
}

function FieldWrapper({
  id,
  label,
  help,
  error,
  touched,
  children,
}: {
  id: string;
  label: string;
  help?: string;
  error?: string;
  touched?: boolean;
  children: ReactNode;
}) {
  const hasError = Boolean(touched && error);
  return (
    <div className="vaic-form-field">
      <label htmlFor={id} className="vaic-form-label">
        {label}
        <span className="vaic-form-required" aria-label="required">
          *
        </span>
      </label>
      {help && (
        <p id={`${id}-help`} className="vaic-form-help">
          {help}
        </p>
      )}
      {children}
      {hasError && (
        <div className="vaic-form-error-text" role="alert">
          {error}
        </div>
      )}
    </div>
  );
}

export default function IdentityTab({
  agentId,
  isNew,
  agent,
  onDirtyChange,
  onSaved,
  onCancelNew,
}: IdentityTabProps) {
  const initial = toFormState(agent);
  const [form, setForm] = useState<FormState>(initial);
  const [errors, setErrors] = useState<Partial<Record<keyof FormState, string>>>({});
  const [touched, setTouched] = useState<Partial<Record<keyof FormState, boolean>>>({});
  const [saveError, setSaveError] = useState<string | null>(null);

  const { editing, startEdit, stopEdit } = useEditMode(isNew);
  const { data: departments } = useDepartments();
  const { update, create } = useAgentMutations(agentId);
  const { show } = useToast();

  // Resync the form baseline whenever the underlying Agent record changes
  // (initial load, or after a successful save).
  useEffect(() => {
    setForm(toFormState(agent));
    setErrors({});
    setTouched({});
  }, [agent]);

  const isDirty =
    form.name !== initial.name ||
    form.departmentId !== initial.departmentId ||
    form.systemPrompt !== initial.systemPrompt ||
    form.status !== initial.status;

  useEffect(() => {
    onDirtyChange(isDirty);
  }, [isDirty, onDirtyChange]);

  function handleReset() {
    setForm(initial);
    setErrors({});
    setTouched({});
    setSaveError(null);
  }

  function handleCancel() {
    handleReset();
    if (isNew) {
      onCancelNew?.();
    } else {
      stopEdit();
    }
  }

  useRegisterTab("identity", { isDirty, save: handleSave, reset: handleReset });

  function handleBlur(field: "name" | "departmentId" | "systemPrompt", label: string) {
    setTouched((t) => ({ ...t, [field]: true }));
    setErrors((e) => ({ ...e, [field]: validateRequired(form[field], label) ?? undefined }));
  }

  async function handleSave() {
    const nameError = validateRequired(form.name, "Name");
    const deptError = validateRequired(form.departmentId, "Department");
    const promptError = validateRequired(form.systemPrompt, "System prompt");

    setTouched({ name: true, departmentId: true, systemPrompt: true });
    setErrors({
      name: nameError ?? undefined,
      departmentId: deptError ?? undefined,
      systemPrompt: promptError ?? undefined,
    });

    if (nameError || deptError || promptError) return;

    setSaveError(null);
    const payload = {
      name: form.name,
      department_id: form.departmentId,
      system_prompt: form.systemPrompt,
      status: form.status,
    };

    try {
      const saved = isNew
        ? await create.mutateAsync(payload)
        : await update.mutateAsync(payload);
      show("Agent saved");
      stopEdit();
      onSaved?.(saved);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Failed to save Agent");
    }
  }

  const isSaving = update.isPending || create.isPending;

  return (
    <div data-testid="vaic-identity-tab">
      <FieldWrapper
        id="vaic-identity-name"
        label="Name"
        help="How this Agent appears in lists and workflows — e.g. Loan Screener."
        error={errors.name}
        touched={touched.name}
      >
        <input
          id="vaic-identity-name"
          className={`vaic-form-input vaic-focusable ${touched.name && errors.name ? "vaic-form-input-error" : ""}`}
          value={form.name}
          disabled={!editing}
          onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
          onBlur={() => handleBlur("name", "Name")}
          aria-invalid={Boolean(touched.name && errors.name)}
          aria-describedby="vaic-identity-name-help"
        />
      </FieldWrapper>

      <FieldWrapper
        id="vaic-identity-department"
        label="Department"
        help="Which org unit owns this Agent. Controls access and grouping."
        error={errors.departmentId}
        touched={touched.departmentId}
      >
        <select
          id="vaic-identity-department"
          className={`vaic-form-input vaic-focusable ${touched.departmentId && errors.departmentId ? "vaic-form-input-error" : ""}`}
          value={form.departmentId}
          disabled={!editing}
          onChange={(e) => setForm((f) => ({ ...f, departmentId: e.target.value }))}
          onBlur={() => handleBlur("departmentId", "Department")}
          aria-describedby="vaic-identity-department-help"
        >
          <option value="">Select a Department</option>
          {(departments ?? []).map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </select>
      </FieldWrapper>

      <FieldWrapper
        id="vaic-identity-system-prompt"
        label="System Prompt"
        help="The Agent's core instructions — role, tone, and rules it always follows. You can refine this later in the Prompt tab."
        error={errors.systemPrompt}
        touched={touched.systemPrompt}
      >
        <textarea
          id="vaic-identity-system-prompt"
          rows={6}
          className={`vaic-form-input vaic-focusable ${touched.systemPrompt && errors.systemPrompt ? "vaic-form-input-error" : ""}`}
          value={form.systemPrompt}
          disabled={!editing}
          onChange={(e) => setForm((f) => ({ ...f, systemPrompt: e.target.value }))}
          onBlur={() => handleBlur("systemPrompt", "System prompt")}
          aria-describedby="vaic-identity-system-prompt-help"
        />
        <div
          className="vaic-form-help"
          data-testid="vaic-identity-prompt-char-count"
          style={{ textAlign: "right" }}
        >
          {form.systemPrompt.length.toLocaleString()} characters
        </div>
      </FieldWrapper>

      <div className="vaic-form-field">
        <span className="vaic-form-label" id="vaic-identity-status-label">
          Status
        </span>
        <p className="vaic-form-help">
          Draft Agents stay hidden from workflows until set to Active.
        </p>
        <div
          className="vaic-segmented"
          role="group"
          aria-labelledby="vaic-identity-status-label"
        >
          {(["draft", "active"] as const).map((s) => (
            <button
              key={s}
              type="button"
              className="vaic-segmented-option vaic-focusable"
              aria-pressed={form.status === s}
              disabled={!editing}
              onClick={() => setForm((f) => ({ ...f, status: s }))}
            >
              {s === "draft" ? "Draft" : "Active"}
            </button>
          ))}
        </div>
      </div>

      {saveError && (
        <div className="vaic-inline-alert" role="alert" data-testid="vaic-identity-save-error">
          {saveError}
        </div>
      )}

      {/* View → Edit → Save/Cancel. Save is the single Primary while editing
          (only one tab mounts at a time, so the UX-DR3 count stays at 1). */}
      <FieldEditActions
        editing={editing}
        isNew={isNew}
        onEdit={startEdit}
        onSave={handleSave}
        onCancel={handleCancel}
        saving={isSaving}
      />
    </div>
  );
}
