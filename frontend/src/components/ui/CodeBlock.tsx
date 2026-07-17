/* Story 1.9 — CodeBlock primitive (UX-DR7).
 *
 * Copy button top-right; syntax highlighting via shiki (client-side, server-quality).
 * bg-surface-inset, text-mono-small, padding 12px, radius 8px per design system.
 *
 * Shiki is loaded lazily so the heavy highlighter only initializes when a
 * CodeBlock actually mounts. If shiki fails or is still loading, we show
 * unstyled <pre> as a fallback so content is never blocked.
 */

import { useEffect, useRef, useState, type CSSProperties } from "react";
import { Copy, Check } from "lucide-react";
import { ICON_STROKE_WIDTH } from "../../lib/icons";

export interface CodeBlockProps {
  /** The code / JSON text to render. */
  code: string;
  /** Language for syntax highlighting (e.g. "json", "python", "typescript"). */
  language?: string;
  /** Optional filename or label shown in the header. */
  label?: string;
  /** Show line numbers. Defaults to false. */
  showLineNumbers?: boolean;
  /** Inline style override for the container. */
  style?: CSSProperties;
}

export default function CodeBlock({
  code,
  language = "json",
  label,
  showLineNumbers = false,
  style,
}: CodeBlockProps) {
  const [highlighted, setHighlighted] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const copyTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Lazily highlight via shiki. If shiki isn't available, we fall back to plain text.
  useEffect(() => {
    let cancelled = false;
    async function highlight() {
      try {
        const { createHighlighter } = await import("shiki");
        const highlighter = await createHighlighter({
          themes: ["github-dark"],
          langs: [language],
        });
        const html = highlighter.codeToHtml(code, {
          lang: language,
          theme: "github-dark",
        });
        if (!cancelled) setHighlighted(html);
        highlighter.dispose();
      } catch {
        // Fallback: no highlighting. Content still visible in plain <pre>.
        if (!cancelled) setHighlighted(null);
      }
    }
    highlight();
    return () => {
      cancelled = true;
    };
  }, [code, language]);

  // Cleanup copy timeout on unmount.
  useEffect(() => {
    return () => {
      if (copyTimeoutRef.current) clearTimeout(copyTimeoutRef.current);
    };
  }, []);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      if (copyTimeoutRef.current) clearTimeout(copyTimeoutRef.current);
      copyTimeoutRef.current = setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard API not available in all environments (e.g. non-secure contexts).
      // Fall back to a temporary textarea.
      const textarea = document.createElement("textarea");
      textarea.value = code;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      try {
        document.execCommand("copy");
        setCopied(true);
        if (copyTimeoutRef.current) clearTimeout(copyTimeoutRef.current);
        copyTimeoutRef.current = setTimeout(() => setCopied(false), 2000);
      } catch {
        // Give up silently — still visible content.
      }
      document.body.removeChild(textarea);
    }
  }

  const lines = code.split("\n");

  return (
    <div className="vaic-code-block" style={style} data-testid="vaic-code-block">
      {(label || showLineNumbers) && (
        <div
          className="text-caption"
          style={{
            color: "var(--color-text-tertiary)",
            marginBottom: "var(--space-2)",
            fontFamily: "var(--font-mono)",
          }}
        >
          {label}
        </div>
      )}
      <button
        type="button"
        className="vaic-code-copy-btn vaic-focusable"
        onClick={handleCopy}
        aria-label={copied ? "Copied" : "Copy code to clipboard"}
        data-testid="vaic-code-copy"
      >
        {copied ? (
          <Check size={14} strokeWidth={ICON_STROKE_WIDTH} />
        ) : (
          <Copy size={14} strokeWidth={ICON_STROKE_WIDTH} />
        )}
      </button>
      {highlighted ? (
        <div dangerouslySetInnerHTML={{ __html: highlighted }} />
      ) : (
        <pre>
          {showLineNumbers
            ? lines.map((line, i) => (
                <div key={i} style={{ display: "flex" }}>
                  <span
                    style={{
                      width: "2em",
                      textAlign: "right",
                      paddingRight: "var(--space-2)",
                      color: "var(--color-text-tertiary)",
                      userSelect: "none",
                      flexShrink: 0,
                    }}
                  >
                    {i + 1}
                  </span>
                  <span>{line}</span>
                </div>
              ))
            : code}
        </pre>
      )}
    </div>
  );
}
