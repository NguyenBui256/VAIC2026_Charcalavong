/* Story 4.7 — Mini-App catalog page (/mini-apps): list-only landing + create modal.
 *
 * Mirrors routes/workflows.tsx structure (TanStack Query, ui primitives,
 * loading/empty/error states). Create flow lives in CreateMiniAppModal,
 * opened from the "Create Mini-App" button (Task 8).
 *
 * "View generated code" is deferred — it needs a backend
 * `GET /mini-apps/{id}/source` route that doesn't exist yet (YAGNI).
 */

import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Button, Card, EmptyState, ErrorState, Skeleton, StatusPill } from "../components/ui";
import type { RunState } from "../lib/icons";
import { semanticIcons, ICON_STROKE_WIDTH } from "../lib/icons";
import { listMiniApps, type MiniApp } from "../lib/miniAppsApi";
import CreateMiniAppModal from "../components/mini-apps/CreateMiniAppModal";

/** Maps the Mini-App build lifecycle onto the shared RunState vocabulary
 * so StatusPill renders the same icon/color language as Runs/Tasks. */
const BUILD_STATUS_TO_RUN_STATE: Record<MiniApp["build_status"], RunState> = {
  pending: "pending",
  building: "running",
  ready: "success",
  failed: "error",
};

const TIER_LABELS: Record<MiniApp["visibility_tier"], string> = {
  public: "Public",
  need_auth: "Need Auth",
  private: "Private",
};

export function MiniAppsPage() {
  const query = useQuery<MiniApp[], Error>({
    queryKey: ["mini-apps"],
    queryFn: listMiniApps,
  });
  const [showCreate, setShowCreate] = useState(false);

  const apps = query.data ?? [];
  const isLoading = query.isLoading;
  const isError = query.isError;
  const isEmpty = !isLoading && !isError && apps.length === 0;
  const MiniAppIcon = semanticIcons.MiniApp;

  function renderList() {
    if (isError) {
      return (
        <ErrorState
          message={query.error?.message ?? "Failed to load Mini-Apps"}
          retry={
            <Button variant="secondary" onClick={() => query.refetch()}>
              Retry
            </Button>
          }
        />
      );
    }
    if (isLoading) {
      return (
        <div
          data-testid="vaic-mini-apps-loading"
          style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}
        >
          <Skeleton height="80px" />
          <Skeleton height="80px" />
          <Skeleton height="80px" />
        </div>
      );
    }
    if (isEmpty) {
      return (
        <EmptyState
          icon={<MiniAppIcon size={48} strokeWidth={ICON_STROKE_WIDTH} />}
          title="No Mini-Apps yet."
          description="Create your first Mini-App with the button above."
        />
      );
    }
    return (
      <div
        data-testid="vaic-mini-apps-grid"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
          gap: "var(--space-3)",
        }}
      >
        {apps.map((app) => (
          <Card
            key={app.id}
            title={app.name}
            subtitle={TIER_LABELS[app.visibility_tier]}
            headerAction={<StatusPill state={BUILD_STATUS_TO_RUN_STATE[app.build_status]} />}
          >
            {app.description && (
              <p
                className="text-small"
                style={{ color: "var(--color-text-tertiary)", marginBottom: "var(--space-2)" }}
              >
                {app.description}
              </p>
            )}
            <Link
              to={`/mini-apps/${app.id}`}
              className="vaic-btn vaic-btn-secondary vaic-focusable"
              style={{ textDecoration: "none", display: "inline-flex" }}
            >
              Open
            </Link>
          </Card>
        ))}
      </div>
    );
  }

  return (
    <div data-testid="vaic-mini-apps-page">
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          marginBottom: "var(--space-4)",
        }}
      >
        <div>
          <h1 className="text-h1" style={{ marginBottom: "var(--space-1)" }}>
            Mini-Apps
          </h1>
          <p className="text-body" style={{ color: "var(--color-text-tertiary)" }}>
            Lightweight, LLM-generated data apps scoped to your Tenant.
          </p>
        </div>
        <Button variant="primary" onClick={() => setShowCreate(true)}>
          Create Mini-App
        </Button>
      </header>

      {renderList()}

      {showCreate && <CreateMiniAppModal onClose={() => setShowCreate(false)} />}
    </div>
  );
}

export default MiniAppsPage;
