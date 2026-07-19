/* Story 2.6 T6.5 — "Test Tool" affordance (AC7).
 *
 * Enter sample_input JSON, invoke the SAME registration -> input-validate ->
 * (sandbox|MCP) -> output-validate path as a real invocation, render the
 * structured success output or validation/sandbox error. UX-DR23 loading/error.
 */

import { useState } from "react";
import { Button, CodeBlock } from "../ui";
import type { ToolTestResult } from "../../lib/toolsApi";

export interface ToolTestPanelProps {
  onRun: (sampleInput: Record<string, unknown>) => Promise<ToolTestResult>;
  isRunning: boolean;
}

export default function ToolTestPanel({ onRun, isRunning }: ToolTestPanelProps) {
  const [sampleInputText, setSampleInputText] = useState("{}");
  const [parseError, setParseError] = useState<string | null>(null);
  const [result, setResult] = useState<ToolTestResult | null>(null);
  const [runError, setRunError] = useState<string | null>(null);

  async function handleRun() {
    let sampleInput: Record<string, unknown>;
    try {
      sampleInput = JSON.parse(sampleInputText);
    } catch (err) {
      setParseError(err instanceof Error ? err.message : "Invalid JSON");
      return;
    }
    setParseError(null);
    setRunError(null);
    setResult(null);
    try {
      const r = await onRun(sampleInput);
      setResult(r);
    } catch (err) {
      setRunError(err instanceof Error ? err.message : "Test Tool invocation failed");
    }
  }

  return (
    <div data-testid="vaic-tool-test-panel" style={{ marginTop: "var(--space-4)" }}>
      <h4 className="text-h4">Test Tool</h4>
      <div className="vaic-form-field">
        <label htmlFor="vaic-tool-test-input" className="vaic-form-label">
          Sample input (JSON)
        </label>
        <textarea
          id="vaic-tool-test-input"
          rows={4}
          className="vaic-form-input vaic-focusable"
          style={{ fontFamily: "var(--font-mono)" }}
          value={sampleInputText}
          onChange={(e) => setSampleInputText(e.target.value)}
        />
        {parseError && (
          <div className="vaic-form-error-text" role="alert">
            {parseError}
          </div>
        )}
      </div>

      <Button variant="secondary" onClick={handleRun} disabled={isRunning}>
        {isRunning ? "Running…" : "Run Test"}
      </Button>

      {runError && (
        <div
          className="vaic-inline-alert"
          role="alert"
          data-testid="vaic-tool-test-error"
          style={{ marginTop: "var(--space-3)" }}
        >
          {runError}
        </div>
      )}

      {result && (
        <div style={{ marginTop: "var(--space-3)" }} data-testid="vaic-tool-test-result">
          {result.success ? (
            <CodeBlock code={JSON.stringify(result.output, null, 2)} language="json" label="Output" />
          ) : (
            <div className="vaic-inline-alert vaic-inline-alert-error" role="alert">
              {result.error || "Test Tool invocation failed"}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
