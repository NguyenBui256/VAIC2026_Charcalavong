/* Story 2.6 T6.4 — Tool registration/edit form (AC1, AC6).
 *
 * display_name, description, IntegrationSelect (integration_id),
 * params_schema/output_schema JSON editors with live client-side lint
 * (AC6 — see Dev Notes T6.6: a full monaco-editor integration was scoped
 * out in favor of a lightweight textarea + `jsonSchemaLint` pre-check,
 * flagged as an Open Question in the completion report — monaco is a
 * large, hard-to-test-in-jsdom dependency for a feature whose correctness
 * is authoritatively enforced server-side at registration time (T2.1)
 * regardless of what the client shows). Reuses Story 2.2 dirty/toast/
 * confirm machinery.
 *
 * Shared-pool version (Plan 2026-07-18 Task 6): tenant-level pool Tool —
 * no `agentId`, mutations from `useCatalogToolMutations()` (`/tools`).
 * `header.auth`/`embedded_python` dropped: pool Tools created here are
 * always `kind: "integration"` (auth lives on the linked Integration;
 * `builtin` Tools are read-only, no editor).
 */

import { useEffect, useState } from "react";
import { Button, useToast } from "../ui";
import { lintJsonSchema } from "../../lib/jsonSchemaLint";
import { useCatalogToolMutations } from "../../hooks/useCatalogTools";
import IntegrationSelect from "./IntegrationSelect";
import ToolTestPanel from "./ToolTestPanel";
import type { Tool } from "../../lib/toolsApi";

export interface ToolEditorProps {
  tool: Tool | null;
  onClose: () => void;
}

function stringifySchema(schema: Record<string, unknown> | undefined): string {
  return JSON.stringify(schema ?? { type: "object", properties: {} }, null, 2);
}

export default function ToolEditor({ tool, onClose }: ToolEditorProps) {
  const isNew = tool === null;
  const [displayName, setDisplayName] = useState(tool?.display_name ?? "");
  const [description, setDescription] = useState(tool?.description ?? "");
  const [paramsSchemaText, setParamsSchemaText] = useState(stringifySchema(tool?.params_schema));
  const [outputSchemaText, setOutputSchemaText] = useState(stringifySchema(tool?.output_schema));
  const [integrationId, setIntegrationId] = useState(tool?.integration_id ?? "");
  const [saveError, setSaveError] = useState<string | null>(null);

  const { create, update, test } = useCatalogToolMutations();
  const { show } = useToast();

  useEffect(() => {
    setDisplayName(tool?.display_name ?? "");
    setDescription(tool?.description ?? "");
    setParamsSchemaText(stringifySchema(tool?.params_schema));
    setOutputSchemaText(stringifySchema(tool?.output_schema));
    setIntegrationId(tool?.integration_id ?? "");
  }, [tool]);

  const paramsLint = lintJsonSchema(paramsSchemaText);
  const outputLint = lintJsonSchema(outputSchemaText);
  const nameError = displayName.trim() ? null : "Display name is required";
  const integrationError = integrationId ? null : "API Integration is required";
  const canSave = !nameError && !integrationError && paramsLint.valid && outputLint.valid;

  async function handleSave() {
    if (!canSave || !paramsLint.parsed || !outputLint.parsed) return;
    setSaveError(null);
    const payload = {
      display_name: displayName,
      description,
      params_schema: paramsLint.parsed,
      output_schema: outputLint.parsed,
      integration_id: integrationId,
    };
    try {
      if (isNew) {
        await create.mutateAsync(payload);
      } else {
        await update.mutateAsync({ toolId: tool!.id, patch: payload });
      }
      show("Tool saved");
      onClose();
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Failed to save Tool");
    }
  }

  const isSaving = create.isPending || update.isPending;

  return (
    <div data-testid="vaic-tool-editor" style={{ marginTop: "var(--space-4)" }}>
      <div className="vaic-form-field">
        <label htmlFor="vaic-tool-display-name" className="vaic-form-label">
          Display name
          <span className="vaic-form-required" aria-label="required">
            *
          </span>
        </label>
        <input
          id="vaic-tool-display-name"
          className="vaic-form-input vaic-focusable"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
        />
        {nameError && (
          <div className="vaic-form-error-text" role="alert">
            {nameError}
          </div>
        )}
      </div>

      <div className="vaic-form-field">
        <label htmlFor="vaic-tool-description" className="vaic-form-label">
          Description
        </label>
        <textarea
          id="vaic-tool-description"
          rows={2}
          className="vaic-form-input vaic-focusable"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </div>

      <IntegrationSelect value={integrationId} onChange={setIntegrationId} />
      {integrationError && (
        <div className="vaic-form-error-text" role="alert">
          {integrationError}
        </div>
      )}

      <SchemaField
        id="vaic-tool-params-schema"
        label="Params schema (JSON Schema draft 2020-12)"
        value={paramsSchemaText}
        onChange={setParamsSchemaText}
        error={paramsLint.error}
      />

      <SchemaField
        id="vaic-tool-output-schema"
        label="Output schema (JSON Schema draft 2020-12)"
        value={outputSchemaText}
        onChange={setOutputSchemaText}
        error={outputLint.error}
      />

      {saveError && (
        <div className="vaic-inline-alert" role="alert" data-testid="vaic-tool-save-error">
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

      {!isNew && tool && (
        <ToolTestPanel
          isRunning={test.isPending}
          onRun={(sampleInput) => test.mutateAsync({ toolId: tool.id, sampleInput })}
        />
      )}
    </div>
  );
}

function SchemaField({
  id,
  label,
  value,
  onChange,
  error,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  error: string | null;
}) {
  return (
    <div className="vaic-form-field">
      <label htmlFor={id} className="vaic-form-label">
        {label}
      </label>
      <textarea
        id={id}
        rows={8}
        className={`vaic-form-input vaic-focusable ${error ? "vaic-form-input-error" : ""}`}
        style={{ fontFamily: "var(--font-mono)" }}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-invalid={Boolean(error)}
      />
      {error && (
        <div className="vaic-form-error-text" role="alert">
          {error}
        </div>
      )}
    </div>
  );
}
