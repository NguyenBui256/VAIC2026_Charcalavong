/* Story 1.8 — Inspector panel (320px right).
 * Optional context-detail panel. Placeholder for Stories 1.9+.
 */

interface InspectorProps {
  open?: boolean;
}

const panelStyle: React.CSSProperties = {
  width: "var(--inspector-w)",
  flexShrink: 0,
  background: "var(--color-surface)",
  borderLeft: "1px solid var(--color-border)",
  padding: "var(--space-4)",
  overflowY: "auto",
};

const headerStyle: React.CSSProperties = {
  fontSize: "var(--text-caption)",
  fontWeight: 600,
  textTransform: "uppercase",
  letterSpacing: "0.04em",
  color: "var(--color-text-tertiary)",
  marginBottom: "var(--space-3)",
};

const placeholderStyle: React.CSSProperties = {
  color: "var(--color-text-tertiary)",
  fontSize: "var(--text-small)",
  lineHeight: "var(--leading-small)",
};

export default function Inspector({ open = false }: InspectorProps) {
  if (!open) return null;

  return (
    <aside className="vaic-inspector" style={panelStyle} data-testid="vaic-inspector">
      <div style={headerStyle}>Inspector</div>
      <p style={placeholderStyle}>
        Context details appear here in Stories 1.9+.
        Select an item to inspect its properties.
      </p>
    </aside>
  );
}
