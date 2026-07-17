/* Story 2.6 T6.4 — Tool registration/edit form (AC1, AC6).
 *
 * display_name, header.auth (masked toggle, UX-DR8), input_schema/output_schema
 * JSON editors with live client-side lint (AC6 — see Dev Notes T6.6: a full
 * monaco-editor integration was scoped out in favor of a lightweight textarea +
 * `jsonSchemaLint` pre-check, flagged as an Open Question in the completion
 * report — monaco is a large, hard-to-test-in-jsdom dependency for a feature
 * whose correctness is authoritatively enforced server-side at registration
 * time (T2.1) regardless of what the client shows), and an optional
 * embedded_python code field. Reuses Story 2.2 dirty/toast/confirm machinery.
 */

import { useEffect, useState } from "react";
import { Button, useToast } from "../ui";
import { lintJsonSchema } from "../../lib/jsonSchemaLint";
import { useAgentToolMutations } from "../../hooks/useAgentTools";
import IntegrationSelect from "./IntegrationSelect";
import ToolTestPanel from "./ToolTestPanel";
import type { Tool } from "../../lib/toolsApi";

export interface ToolEditorProps {
  agentId: string;
  tool: Tool | null;
  onClose: () => void;
}

function stringifySchema(schema: Record<string, unknown> | undefined): string {
  return JSON.stringify(schema ?? { type: "object", properties: {} }, null, 2);
}

export default function ToolEditor({ agentId, tool, onClose }: ToolEditorProps) {
  const isNew = tool === null;
  const [displayName, setDisplayName] = useState(tool?.display_name ?? "");
  const [hasAuth, setHasAuth] = useState(Boolean(tool?.header?.auth));
  const [inputSchemaText, setInputSchemaText] = useState(stringifySchema(tool?.input_schema));
  const [outputSchemaText, setOutputSchemaText] = useState(stringifySchema(tool?.output_schema));
  const [useEmbeddedPython, setUseEmbeddedPython] = useState(tool?.kind === "embedded_python");
  const [embeddedPython, setEmbeddedPython] = useState("");
  const [integrationId, setIntegrationId] = useState(tool?.integration_id ?? "");
  const [saveError, setSaveError] = useState<string | null>(null);

  const { create, update, test } = useAgentToolMutations(agentId);
  const { show } = useToast();

  useEffect(() => {
    setDisplayName(tool?.display_name ?? "");
    setHasAuth(Boolean(tool?.header?.auth));
    setInputSchemaText(stringifySchema(tool?.input_schema));
    setOutputSchemaText(stringifySchema(tool?.output_schema));
    setUseEmbeddedPython(tool?.kind === "embedded_python");
    setIntegrationId(tool?.integration_id ?? "");
  }, [tool]);

  const inputLint = lintJsonSchema(inputSchemaText);
  const outputLint = lintJsonSchema(outputSchemaText);
  const nameError = displayName.trim() ? null : "Display name is required";
  const canSave = !nameError && inputLint.valid && outputLint.valid;

  async function handleSave() {
    if (!canSave || !inputLint.parsed || !outputLint.parsed) return;
    setSaveError(null);
    const payload = {
      display_name: displayName,
      header: hasAuth ? { auth: { type: "bearer" } } : {},
      input_schema: inputLint.parsed,
      output_schema: outputLint.parsed,
      embedded_python: useEmbeddedPython ? embeddedPython : null,
      integration_id: integrationId || null,
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
        <label className="vaic-form-label" htmlFor="vaic-tool-has-auth">
          <input
            id="vaic-tool-has-auth"
            type="checkbox"
            checked={hasAuth}
            onChange={(e) => setHasAuth(e.target.checked)}
            style={{ marginRight: "var(--space-2)" }}
          />
          Requires auth (stored, never displayed after save)
        </label>
      </div>

      <IntegrationSelect agentId={agentId} value={integrationId} onChange={setIntegrationId} />

      <SchemaField
        id="vaic-tool-input-schema"
        label="Input schema (JSON Schema draft 2020-12)"
        value={inputSchemaText}
        onChange={setInputSchemaText}
        error={inputLint.error}
      />

      <SchemaField
        id="vaic-tool-output-schema"
        label="Output schema (JSON Schema draft 2020-12)"
        value={outputSchemaText}
        onChange={setOutputSchemaText}
        error={outputLint.error}
      />

      <div className="vaic-form-field">
        <label className="vaic-form-label" htmlFor="vaic-tool-use-embedded-python">
          <input
            id="vaic-tool-use-embedded-python"
            type="checkbox"
            checked={useEmbeddedPython}
            onChange={(e) => setUseEmbeddedPython(e.target.checked)}
            style={{ marginRight: "var(--space-2)" }}
          />
          Embedded Python (sandboxed — no network, 10s CPU / 128MB caps)
        </label>
        {useEmbeddedPython && (
          <textarea
            id="vaic-tool-embedded-python-source"
            rows={8}
            className="vaic-form-input vaic-focusable"
            style={{ fontFamily: "var(--font-mono)" }}
            value={embeddedPython}
            onChange={(e) => setEmbeddedPython(e.target.value)}
            placeholder="import sys, json&#10;data = json.loads(sys.stdin.read())&#10;print(json.dumps({...}))"
          />
        )}
      </div>

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
