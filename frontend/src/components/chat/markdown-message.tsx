/* Renders assistant markdown safely (react-markdown, no raw HTML).
 * Fenced code blocks reuse the shiki-backed CodeBlock primitive.
 */

import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { CodeBlock } from "../ui";

const components: Components = {
  code({ node, className, children, ...props }) {
    const match = /language-(\w+)/.exec(className || "");
    const text = String(children ?? "").replace(/\n$/, "");
    // Fenced block (has language OR contains newline) → CodeBlock.
    const isBlock = Boolean(match) || text.includes("\n");
    if (isBlock) {
      return (
        <CodeBlock
          code={text}
          language={match ? match[1] : "text"}
          style={{ margin: "var(--space-2) 0" }}
        />
      );
    }
    return (
      <code
        style={{
          background: "var(--color-surface-inset, var(--color-surface-muted))",
          padding: "0.1em 0.35em",
          borderRadius: "var(--radius-control, 6px)",
          fontFamily: "var(--font-mono)",
          fontSize: "0.9em",
        }}
        {...props}
      >
        {children}
      </code>
    );
  },
  pre: ({ children }) => <>{children}</>,
};

export default function MarkdownMessage({ content }: { content: string }) {
  return (
    <div className="vaic-md text-body" style={{ lineHeight: 1.6 }}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
