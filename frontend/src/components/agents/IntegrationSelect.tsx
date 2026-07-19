/* Story 2.7 T8.1 — reusable "API Integration" dropdown (AC3).
 *
 * Shared-pool version (Plan 2026-07-18 Task 6): populated from the
 * tenant-level `useIntegrations()` pool (no more per-agent scoping). Used
 * by `ToolEditor.tsx` so a Tool can reference an `integration_id`.
 */

import { useIntegrations } from "../../hooks/useIntegrations";

export interface IntegrationSelectProps {
  /** Currently selected Integration id, or empty string for "none". */
  value: string;
  onChange: (integrationId: string) => void;
  id?: string;
  label?: string;
}

export default function IntegrationSelect({
  value,
  onChange,
  id = "vaic-integration-select",
  label = "API Integration",
}: IntegrationSelectProps) {
  const { integrations, isLoading } = useIntegrations();

  return (
    <div className="vaic-form-field">
      <label htmlFor={id} className="vaic-form-label">
        {label}
      </label>
      <select
        id={id}
        className="vaic-form-input vaic-focusable"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={isLoading}
      >
        <option value="">None</option>
        {integrations.map((integration) => (
          <option key={integration.id} value={integration.id}>
            {integration.name}
          </option>
        ))}
      </select>
    </div>
  );
}
