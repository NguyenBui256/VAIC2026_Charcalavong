/* Story 2.7 T7.3 — API Integration registration/edit form (AC1, AC2, UX-DR8).
 *
 * Name, Base URL (required), Auth Header (write-only password-style input —
 * blank on edit means "keep the stored value unchanged"; shown masked after
 * save via `auth_header_masked`), Schema (JSON textarea, optional). Mirrors
 * `ToolEditor.tsx` structure (Story 2.6) and reuses Story 2.2 toast/dirty
 * machinery.
 *
 * Shared-pool version (Plan 2026-07-18 Task 6): tenant-level, no `agentId` —
 * mutations come from `useIntegrationMutations()` (pool CRUD, `/integrations`).
 */

import { useEffect, useState } from "react";
import { Button, useToast } from "../ui";
import { useIntegrationMutations } from "../../hooks/useIntegrationMutations";
import type { ApiIntegration } from "../../lib/integrationsApi";

export interface IntegrationEditorProps {
  integration: ApiIntegration | null;
  onClose: () => void;
}

function stringifySchema(schema: Record<string, unknown> | null | undefined): string {
  return schema ? JSON.stringify(schema, null, 2) : "";
}

function parseSchema(text: string): { valid: boolean; parsed: Record<string, unknown> | null; error: string | null } {
  if (!text.trim()) return { valid: true, parsed: null, error: null };
  try {
    return { valid: true, parsed: JSON.parse(text), error: null };
  } catch {
    return { valid: false, parsed: null, error: "Schema must be valid JSON" };
  }
}

export default function IntegrationEditor({ integration, onClose }: IntegrationEditorProps) {
  const isNew = integration === null;
  const [name, setName] = useState(integration?.name ?? "");
  const [baseUrl, setBaseUrl] = useState(integration?.base_url ?? "");
  const [authHeader, setAuthHeader] = useState("");
  const [schemaText, setSchemaText] = useState(stringifySchema(integration?.schema));
  const [touched, setTouched] = useState({ name: false, baseUrl: false, authHeader: false });
  const [saveError, setSaveError] = useState<string | null>(null);

  const { create, update } = useIntegrationMutations();
  const { show } = useToast();

  useEffect(() => {
    setName(integration?.name ?? "");
    setBaseUrl(integration?.base_url ?? "");
    setAuthHeader("");
    setSchemaText(stringifySchema(integration?.schema));
  }, [integration]);

  const nameError = name.trim() ? null : "Name is required";
  const baseUrlError = baseUrl.trim() ? null : "Base URL is required";
  const authHeaderError = isNew && !authHeader.trim() ? "Auth header is required" : null;
  const schemaLint = parseSchema(schemaText);
  const canSave = !nameError && !baseUrlError && !authHeaderError && schemaLint.valid;

  async function handleSave() {
    if (!canSave) return;
    setSaveError(null);
    try {
      if (isNew) {
        await create.mutateAsync({
          name,
          base_url: baseUrl,
          auth_header: authHeader,
          schema: schemaLint.parsed,
        });
      } else {
        const patch: Record<string, unknown> = { name, base_url: baseUrl, schema: schemaLint.parsed };
        if (authHeader.trim()) patch.auth_header = authHeader;
        await update.mutateAsync({ integrationId: integration!.id, patch });
      }
      show("Integration saved");
      onClose();
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Failed to save Integration");
    }
  }

  const isSaving = create.isPending || update.isPending;

  return (
    <div data-testid="vaic-integration-editor" style={{ marginTop: "var(--space-4)" }}>
      <TextField
        id="vaic-integration-name"
        label="Name"
        required
        value={name}
        onChange={setName}
        onBlur={() => setTouched((t) => ({ ...t, name: true }))}
        error={touched.name ? nameError : null}
      />

      <TextField
        id="vaic-integration-base-url"
        label="Base URL"
        required
        value={baseUrl}
        onChange={setBaseUrl}
        onBlur={() => setTouched((t) => ({ ...t, baseUrl: true }))}
        error={touched.baseUrl ? baseUrlError : null}
        placeholder="https://stub.example.com/gmail"
      />

      <TextField
        id="vaic-integration-auth-header"
        label="Auth Header"
        type="password"
        required={isNew}
        value={authHeader}
        onChange={setAuthHeader}
        onBlur={() => setTouched((t) => ({ ...t, authHeader: true }))}
        error={touched.authHeader ? authHeaderError : null}
        helperText={
          isNew
            ? "Stored encrypted, never displayed in full after save."
            : `Currently: ${integration?.auth_header_masked ?? "••••"} — leave blank to keep unchanged.`
        }
      />

      <div className="vaic-form-field">
        <label htmlFor="vaic-integration-schema" className="vaic-form-label">
          Schema (JSON, optional)
        </label>
        <textarea
          id="vaic-integration-schema"
          rows={6}
          className={`vaic-form-input vaic-focusable ${schemaLint.error ? "vaic-form-input-error" : ""}`}
          style={{ fontFamily: "var(--font-mono)" }}
          value={schemaText}
          onChange={(e) => setSchemaText(e.target.value)}
          aria-invalid={Boolean(schemaLint.error)}
        />
        {schemaLint.error && (
          <div className="vaic-form-error-text" role="alert">
            {schemaLint.error}
          </div>
        )}
      </div>

      {saveError && (
        <div className="vaic-inline-alert" role="alert" data-testid="vaic-integration-save-error">
          {saveError}
        </div>
      )}

      <div style={{ display: "flex", gap: "var(--space-2)" }}>
        <Button variant="primary" onClick={handleSave} disabled={!canSave || isSaving}>
          Save
        </Button>
        <Button variant="secondary" onClick={onClose}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

function TextField({
  id,
  label,
  value,
  onChange,
  onBlur,
  error,
  required = false,
  type = "text",
  placeholder,
  helperText,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  onBlur: () => void;
  error: string | null;
  required?: boolean;
  type?: string;
  placeholder?: string;
  helperText?: string;
}) {
  return (
    <div className="vaic-form-field">
      <label htmlFor={id} className="vaic-form-label">
        {label}
        {required && (
          <span className="vaic-form-required" aria-label="required">
            *
          </span>
        )}
      </label>
      <input
        id={id}
        type={type}
        className={`vaic-form-input vaic-focusable ${error ? "vaic-form-input-error" : ""}`}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onBlur={onBlur}
        placeholder={placeholder}
        aria-invalid={Boolean(error)}
      />
      {error ? (
        <div className="vaic-form-error-text" role="alert">
          {error}
        </div>
      ) : helperText ? (
        <div className="vaic-form-helper">{helperText}</div>
      ) : null}
    </div>
  );
}
