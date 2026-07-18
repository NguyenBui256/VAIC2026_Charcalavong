/* Database page — two sections: Knowledge Base (agents, reuses the existing
 * tenant-wide KnowledgeBasePage) + Mini-App Databases. Sidebar item now points
 * here (/database). */
import { useState } from "react";
import KnowledgeBasePage from "./knowledge-base/KnowledgeBasePage";
import MiniAppDatabaseSection from "../components/database/MiniAppDatabaseSection";

type Tab = "kb" | "mini-app-db";

const TABS: Array<{ id: Tab; label: string }> = [
  { id: "kb", label: "Knowledge Base" },
  { id: "mini-app-db", label: "Mini-App Databases" },
];

export function DatabasePage() {
  const [tab, setTab] = useState<Tab>("kb");
  return (
    <div data-testid="vaic-database-page">
      <div
        role="tablist"
        aria-label="Database sections"
        style={{ display: "flex", gap: "var(--space-2)", borderBottom: "1px solid var(--color-border)", marginBottom: "var(--space-4)" }}
      >
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            className="vaic-focusable"
            onClick={() => setTab(t.id)}
            style={{
              padding: "var(--space-2) var(--space-3)",
              background: "none",
              border: "none",
              borderBottom: `2px solid ${tab === t.id ? "var(--color-primary)" : "transparent"}`,
              color: tab === t.id ? "var(--color-primary)" : "var(--color-text-secondary)",
              fontWeight: tab === t.id ? 600 : 500,
              cursor: "pointer",
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "kb" ? <KnowledgeBasePage /> : <MiniAppDatabaseSection />}
    </div>
  );
}

export default DatabasePage;
