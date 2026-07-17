/* Story 2.7 T8.1 — reusable "API Integration" dropdown (AC3).
 *
 * Populated from `listIntegrations(agentId)`. Story 2.6's `ToolsTab`/
 * `ToolEditor` consumes this component so a Tool can reference an
 * `integration_id`; the Tool model persisting that field is owned by
 * Story 2.6 (see 2-7 Dev Notes OQ-2 — Tool→Integration wiring seam).
 */

import { useIntegrations } from "../../hooks/useIntegrations";

export interface IntegrationSelectProps {
  agentId: string;
  /** Currently selected Integration id, or empty string for "none". */
  value: string;
  onChange: (integrationId: string) => void;
  id?: string;
  label?: string;
}

export default function IntegrationSelect({
  agentId,
  value,
  onChange,
  id = "vaic-integration-select",
  label = "API Integration",
}: IntegrationSelectProps) {
  const { integrations, isLoading } = useIntegrations(agentId);

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
