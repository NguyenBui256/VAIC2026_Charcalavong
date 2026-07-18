/* Story 3.1 — Definition tab (AC6): Name (required), Description (textarea,
 * required), Constraints (chip-list, optional). UX-DR8: labels above
 * inputs, required marked `*`, inline validation on blur. Mirrors the
 * Story 2.2 IdentityTab form pattern (FieldWrapper, validate-on-blur +
 * re-validate-on-save).
 */

import { useEffect, useState, type ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { Button, useToast } from "../ui";
import ConstraintsEditor from "./ConstraintsEditor";
import type { Workflow } from "../../lib/workflowsApi";
import { useWorkflowMutations } from "../../hooks/useWorkflowMutations";
import { getTemplate, type CreateSeed } from "../../lib/graphTemplates";
import { putWorkflowGraph } from "../../lib/workflowGraphApi";

export interface DefinitionTabProps {
  workflowId: string;
  isNew: boolean;
  workflow: Workflow | undefined;
  onDirtyChange: (dirty: boolean) => void;
  onSaved?: (workflow: Workflow) => void;
}

interface FormState {
  name: string;
  description: string;
  constraints: string[];
}

function toFormState(workflow: Workflow | undefined): FormState {
  return {
    name: workflow?.name ?? "",
    description: workflow?.description ?? "",
    constraints: workflow?.constraints ?? [],
  };
}

function validateRequired(value: string, label: string): string | null {
  return value.trim() ? null : `${label} is required`;
}

function FieldWrapper({
  id,
  label,
  error,
  touched,
  children,
}: {
  id: string;
  label: string;
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
      {children}
      {hasError && (
        <div className="vaic-form-error-text" role="alert">
          {error}
        </div>
      )}
    </div>
  );
}

export default function DefinitionTab({
  workflowId,
  isNew,
  workflow,
  onDirtyChange,
  onSaved,
}: DefinitionTabProps) {
  const location = useLocation();
  const seed = isNew ? ((location.state as { seed?: CreateSeed } | null)?.seed ?? null) : null;

  const initial = toFormState(workflow);
  if (isNew && seed && seed.kind !== "blank" && !initial.name) {
    initial.name = seed.defaultName;
  }
  const [form, setForm] = useState<FormState>(initial);
  const [errors, setErrors] = useState<Partial<Record<"name" | "description", string>>>({});
  const [touched, setTouched] = useState<Partial<Record<"name" | "description", boolean>>>({});
  const [saveError, setSaveError] = useState<string | null>(null);

  const { update, create } = useWorkflowMutations(workflowId);
  const { show } = useToast();

  // Resync the form baseline whenever the underlying Workflow record changes
  // (initial load, or after a successful save).
  useEffect(() => {
    setForm(toFormState(workflow));
    setErrors({});
    setTouched({});
  }, [workflow]);

  const isDirty =
    form.name !== initial.name ||
    form.description !== initial.description ||
    JSON.stringify(form.constraints) !== JSON.stringify(initial.constraints);

  useEffect(() => {
    onDirtyChange(isDirty);
  }, [isDirty, onDirtyChange]);

  function handleBlur(field: "name" | "description", label: string) {
    setTouched((t) => ({ ...t, [field]: true }));
    setErrors((e) => ({ ...e, [field]: validateRequired(form[field], label) ?? undefined }));
  }

  async function handleSave() {
    const nameError = validateRequired(form.name, "Name");
    const descriptionError = validateRequired(form.description, "Description");

    setTouched({ name: true, description: true });
    setErrors({
      name: nameError ?? undefined,
      description: descriptionError ?? undefined,
    });

    if (nameError || descriptionError) return;

    setSaveError(null);
    const payload = {
      name: form.name,
      description: form.description,
      constraints: form.constraints,
    };

    try {
      const saved = isNew
        ? await create.mutateAsync(payload)
        : await update.mutateAsync(payload);

      // Seed the new workflow's graph from the chosen template / source.
      if (isNew && seed && seed.kind !== "blank") {
        try {
          const def =
            seed.kind === "template"
              ? getTemplate(seed.templateId)?.build()
              : seed.def;
          if (def) await putWorkflowGraph(saved.id, def);
        } catch (graphErr) {
          // The record exists; surface the seeding failure but still proceed —
          // the user can build the graph manually in the Graph tab.
          show(
            graphErr instanceof Error
              ? `Workflow created, but seeding the graph failed: ${graphErr.message}`
              : "Workflow created, but seeding the graph failed.",
            "error",
          );
        }
      }

      show("Workflow saved");
      onSaved?.(saved);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Failed to save Workflow");
    }
  }

  const isSaving = update.isPending || create.isPending;

  return (
    <div data-testid="vaic-definition-tab">
      <FieldWrapper id="vaic-workflow-name" label="Name" error={errors.name} touched={touched.name}>
        <input
          id="vaic-workflow-name"
          className={`vaic-form-input vaic-focusable ${touched.name && errors.name ? "vaic-form-input-error" : ""}`}
          value={form.name}
          onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
          onBlur={() => handleBlur("name", "Name")}
          aria-invalid={Boolean(touched.name && errors.name)}
        />
      </FieldWrapper>

      <FieldWrapper
        id="vaic-workflow-description"
        label="Description"
        error={errors.description}
        touched={touched.description}
      >
        <textarea
          id="vaic-workflow-description"
          rows={6}
          className={`vaic-form-input vaic-focusable ${touched.description && errors.description ? "vaic-form-input-error" : ""}`}
          value={form.description}
          onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
          onBlur={() => handleBlur("description", "Description")}
          aria-invalid={Boolean(touched.description && errors.description)}
        />
      </FieldWrapper>

      <div className="vaic-form-field">
        <label htmlFor="vaic-workflow-constraints" className="vaic-form-label">
          Constraints
        </label>
        <ConstraintsEditor
          id="vaic-workflow-constraints"
          value={form.constraints}
          onChange={(next) => setForm((f) => ({ ...f, constraints: next }))}
        />
      </div>

      {saveError && (
        <div className="vaic-inline-alert" role="alert" data-testid="vaic-definition-save-error">
          {saveError}
        </div>
      )}

      <Button variant="primary" onClick={handleSave} disabled={isSaving}>
        Save
      </Button>
    </div>
  );
}
