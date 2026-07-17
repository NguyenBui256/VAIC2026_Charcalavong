/* Story 2.3 — Prompt tab (AC #6, #7, #8).
 *
 * Monospace `system_prompt` editor with a highlight overlay for prompt
 * directives (`{{tool:...}}`, `{{kb:...}}`) — only highlighted here;
 * resolution is Stories 2.4-2.6. Live character count + a non-blocking
 * context-window warning (estimated from the Agent's saved Model, via the
 * Story 2.3 T1 catalog). Save PATCHes `{ system_prompt }`.
 */

import { useEffect, useRef, useState } from "react";
import { Button, Card, useToast } from "../../ui";
import { useAgentProviders } from "../../../hooks/useAgentProviders";
import { useAgentMutations } from "../../../hooks/useAgentMutations";
import { useRegisterTab } from "../AgentBuilderContext";
import type { Agent, ModelRef } from "../../../lib/agentsApi";

export interface PromptTabProps {
  agentId: string;
  isNew: boolean;
  agent: Agent | undefined;
  onDirtyChange: (dirty: boolean) => void;
}

// {{tool:rag.search}} / {{kb:agent_id}} — directive token highlight (AC6).
const DIRECTIVE_RE = /\{\{(?:tool|kb):[^}]+\}\}/g;

interface DirectivePart {
  text: string;
  isDirective: boolean;
}

function splitDirectives(text: string): DirectivePart[] {
  const parts: DirectivePart[] = [];
  let lastIndex = 0;
  for (const match of text.matchAll(DIRECTIVE_RE)) {
    const index = match.index ?? 0;
    if (index > lastIndex) parts.push({ text: text.slice(lastIndex, index), isDirective: false });
    parts.push({ text: match[0], isDirective: true });
    lastIndex = index + match[0].length;
  }
  if (lastIndex < text.length) parts.push({ text: text.slice(lastIndex), isDirective: false });
  // A trailing newline needs a rendered char so the overlay's height matches
  // the textarea's (browsers collapse a trailing "\n" in a <pre> otherwise).
  if (text.endsWith("\n")) parts.push({ text: " ", isDirective: false });
  return parts;
}

// Rough chars-per-token estimate for the non-blocking context-window warning.
const CHARS_PER_TOKEN_ESTIMATE = 4;

export default function PromptTab({ agentId, isNew, agent, onDirtyChange }: PromptTabProps) {
  const { data: providers } = useAgentProviders();
  const { update } = useAgentMutations(agentId);
  const { show } = useToast();

  const initial = agent?.system_prompt ?? "";
  const [text, setText] = useState(initial);
  const [saveError, setSaveError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const overlayRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setText(agent?.system_prompt ?? "");
  }, [agent]);

  const isDirty = text !== initial;
  useEffect(() => {
    onDirtyChange(isDirty);
  }, [isDirty, onDirtyChange]);

  function handleReset() {
    setText(initial);
    setSaveError(null);
  }

  useRegisterTab("prompt", { isDirty, save: handleSave, reset: handleReset });

  const model = (agent?.model ?? {}) as Partial<ModelRef>;
  const contextWindow = (providers ?? [])
    .find((p) => p.id === model.provider)
    ?.models.find((m) => m.name === model.model_name)?.context_window;

  const estimatedTokens = Math.ceil(text.length / CHARS_PER_TOKEN_ESTIMATE);
  const exceedsContextWindow = Boolean(contextWindow) && estimatedTokens > (contextWindow as number);

  function handleScroll() {
    if (overlayRef.current && textareaRef.current) {
      overlayRef.current.scrollTop = textareaRef.current.scrollTop;
      overlayRef.current.scrollLeft = textareaRef.current.scrollLeft;
    }
  }

  async function handleSave() {
    setSaveError(null);
    try {
      await update.mutateAsync({ system_prompt: text });
      show("Agent saved");
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Failed to save Agent");
    }
  }

  if (isNew) {
    return (
      <Card title="Prompt">
        <p className="text-body" style={{ color: "var(--color-text-tertiary)" }}>
          Save the Agent's Identity first, then edit its Prompt.
        </p>
      </Card>
    );
  }

  return (
    <div data-testid="vaic-prompt-tab">
      <Card title="Prompt">
        <div
          className="vaic-prompt-editor"
          style={{ position: "relative", fontFamily: "var(--font-mono)" }}
        >
          <div
            ref={overlayRef}
            aria-hidden="true"
            data-testid="vaic-prompt-highlight-overlay"
            className="vaic-prompt-highlight-overlay"
            style={{
              position: "absolute",
              inset: 0,
              margin: 0,
              padding: "var(--space-3)",
              overflow: "hidden",
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
              pointerEvents: "none",
              color: "transparent",
            }}
          >
            {splitDirectives(text).map((part, i) =>
              part.isDirective ? (
                <mark key={i} className="vaic-prompt-directive" data-testid="vaic-prompt-directive">
                  {part.text}
                </mark>
              ) : (
                <span key={i}>{part.text}</span>
              ),
            )}
          </div>
          <textarea
            ref={textareaRef}
            id="vaic-prompt-textarea"
            aria-label="System prompt"
            rows={14}
            className="vaic-form-input vaic-focusable"
            style={{
              position: "relative",
              background: "transparent",
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
            }}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onScroll={handleScroll}
          />
        </div>

        <div
          className="text-small"
          data-testid="vaic-prompt-char-count"
          style={{ color: "var(--color-text-tertiary)", marginTop: "var(--space-2)" }}
        >
          {text.length.toLocaleString()} characters
        </div>

        {exceedsContextWindow && (
          <div
            className="vaic-inline-alert vaic-inline-alert-warning"
            role="status"
            data-testid="vaic-prompt-context-warning"
            style={{ marginTop: "var(--space-2)" }}
          >
            This prompt is ~{estimatedTokens.toLocaleString()} estimated tokens, which exceeds the
            selected model's ~{(contextWindow as number).toLocaleString()}-token context window.
          </div>
        )}

        {saveError && (
          <div className="vaic-inline-alert" role="alert" data-testid="vaic-prompt-save-error">
            {saveError}
          </div>
        )}

        <div style={{ marginTop: "var(--space-3)" }}>
          {/* Secondary weight — the shell's "Save All" is the single Primary CTA (UX-DR3). */}
          <Button variant="secondary" onClick={handleSave} disabled={update.isPending}>
            Save
          </Button>
        </div>
      </Card>
    </div>
  );
}
