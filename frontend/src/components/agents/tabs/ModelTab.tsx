/* Story 2.3 — Model tab (AC #1, #2, #3, #4, #5).
 *
 * Provider dropdown lists the runtime-configured catalog from
 * `GET /agents/providers` (never hard-coded, AD-7/FR-5). Selecting a
 * Provider repopulates the Model dropdown from that provider's `models`.
 * Parameters (temperature, max_tokens) are optional overrides — only keys
 * the user actually touches are sent (AC3). Save PATCHes
 * `{ model: {provider, model_name, parameters} }` — pure data, no code
 * branch per provider (AC4, AC5).
 */

import { useEffect, useState } from "react";
import { Button, Card, useToast } from "../../ui";
import { semanticIcons, ICON_STROKE_WIDTH } from "../../../lib/icons";
import { useAgentProviders } from "../../../hooks/useAgentProviders";
import { useAgentMutations } from "../../../hooks/useAgentMutations";
import type { Agent, ModelRef } from "../../../lib/agentsApi";

export interface ModelTabProps {
  agentId: string;
  isNew: boolean;
  agent: Agent | undefined;
  onDirtyChange: (dirty: boolean) => void;
}

const DEFAULT_MAX_TOKENS = 1024;

interface FormState {
  provider: string;
  modelName: string;
  /** Empty string means "unset" — no override sent for that key (AC3). */
  temperature: string;
  maxTokens: string;
}

function toFormState(agent: Agent | undefined): FormState {
  const model = (agent?.model ?? {}) as Partial<ModelRef>;
  const parameters = model.parameters ?? {};
  return {
    provider: model.provider ?? "",
    modelName: model.model_name ?? "",
    temperature:
      typeof parameters.temperature === "number" ? String(parameters.temperature) : "",
    maxTokens: typeof parameters.max_tokens === "number" ? String(parameters.max_tokens) : "",
  };
}

export default function ModelTab({ agentId, isNew, agent, onDirtyChange }: ModelTabProps) {
  const Icon = semanticIcons.Model;
  const { data: providers, isLoading: providersLoading } = useAgentProviders();
  const { update } = useAgentMutations(agentId);
  const { show } = useToast();

  const initial = toFormState(agent);
  const [form, setForm] = useState<FormState>(initial);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    setForm(toFormState(agent));
  }, [agent]);

  const isDirty =
    form.provider !== initial.provider ||
    form.modelName !== initial.modelName ||
    form.temperature !== initial.temperature ||
    form.maxTokens !== initial.maxTokens;

  useEffect(() => {
    onDirtyChange(isDirty);
  }, [isDirty, onDirtyChange]);

  const selectedProvider = (providers ?? []).find((p) => p.id === form.provider);
  const availableModels = selectedProvider?.models ?? [];

  function handleProviderChange(providerId: string) {
    setForm((f) => ({ ...f, provider: providerId, modelName: "" }));
  }

  async function handleSave() {
    setSaveError(null);
    const parameters: Record<string, unknown> = {};
    if (form.temperature.trim() !== "") parameters.temperature = Number(form.temperature);
    if (form.maxTokens.trim() !== "") parameters.max_tokens = Number(form.maxTokens);

    const model: ModelRef = {
      provider: form.provider,
      model_name: form.modelName,
      parameters,
    };

    try {
      await update.mutateAsync({ model });
      show("Agent saved");
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Failed to save Agent");
    }
  }

  if (isNew) {
    return (
      <Card title="Model">
        <p className="text-body" style={{ color: "var(--color-text-tertiary)" }}>
          Save the Agent's Identity first, then configure its Model.
        </p>
      </Card>
    );
  }

  return (
    <div data-testid="vaic-model-tab">
      <Card
        title="Model"
        headerAction={
          <Icon size={18} strokeWidth={ICON_STROKE_WIDTH} style={{ color: "var(--color-text-tertiary)" }} aria-hidden="true" />
        }
      >
        <div className="vaic-form-field">
          <label htmlFor="vaic-model-provider" className="vaic-form-label">
            Provider
          </label>
          <select
            id="vaic-model-provider"
            className="vaic-form-input vaic-focusable"
            value={form.provider}
            disabled={providersLoading}
            onChange={(e) => handleProviderChange(e.target.value)}
          >
            <option value="">Select a Provider</option>
            {(providers ?? []).map((p) => (
              <option key={p.id} value={p.id} disabled={!p.configured}>
                {p.label}
                {!p.configured ? " (Not configured)" : ""}
              </option>
            ))}
          </select>
        </div>

        <div className="vaic-form-field">
          <label htmlFor="vaic-model-name" className="vaic-form-label">
            Model
          </label>
          <select
            id="vaic-model-name"
            className="vaic-form-input vaic-focusable"
            value={form.modelName}
            disabled={!form.provider || availableModels.length === 0}
            onChange={(e) => setForm((f) => ({ ...f, modelName: e.target.value }))}
          >
            <option value="">Select a Model</option>
            {availableModels.map((m) => (
              <option key={m.name} value={m.name}>
                {m.name}
              </option>
            ))}
          </select>
        </div>

        <fieldset className="vaic-form-field" style={{ border: "none", padding: 0, margin: 0 }}>
          <legend className="vaic-form-label" style={{ marginBottom: "var(--space-2)" }}>
            Parameters
          </legend>
          <div style={{ display: "flex", gap: "var(--space-3)" }}>
            <div style={{ flex: 1 }}>
              <label htmlFor="vaic-model-temperature" className="text-small" style={{ color: "var(--color-text-tertiary)" }}>
                Temperature (default: provider default)
              </label>
              <input
                id="vaic-model-temperature"
                type="number"
                step="0.1"
                min="0"
                max="2"
                className="vaic-form-input vaic-focusable"
                value={form.temperature}
                placeholder="unset"
                onChange={(e) => setForm((f) => ({ ...f, temperature: e.target.value }))}
              />
            </div>
            <div style={{ flex: 1 }}>
              <label htmlFor="vaic-model-max-tokens" className="text-small" style={{ color: "var(--color-text-tertiary)" }}>
                Max tokens (default: {DEFAULT_MAX_TOKENS})
              </label>
              <input
                id="vaic-model-max-tokens"
                type="number"
                min="1"
                className="vaic-form-input vaic-focusable"
                value={form.maxTokens}
                placeholder={String(DEFAULT_MAX_TOKENS)}
                onChange={(e) => setForm((f) => ({ ...f, maxTokens: e.target.value }))}
              />
            </div>
          </div>
        </fieldset>

        {saveError && (
          <div className="vaic-inline-alert" role="alert" data-testid="vaic-model-save-error">
            {saveError}
          </div>
        )}

        <Button variant="primary" onClick={handleSave} disabled={update.isPending || !form.provider || !form.modelName}>
          Save
        </Button>
      </Card>
    </div>
  );
}
