/* Story 4-5 — Sandboxed Mini-App host page (/mini-apps/:appId) (Task 16).
 *
 * Fetches the Mini-App record, polls while it's building, and once
 * `build_status === "ready"` fetches a scoped session token and renders the
 * generated app in a sandboxed iframe. The iframe sandbox intentionally omits
 * `allow-same-origin` — the scoped token passed via the URL hash is the ONLY
 * credential the iframe holds; it must never be able to read the parent's
 * localStorage or platform token.
 */

import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Button, Card, ErrorState, Skeleton, useToast } from "../components/ui";
import { getMiniApp, getScopedToken, type MiniApp } from "../lib/miniAppsApi";
import { useMiniAppDatabases } from "../hooks/useMiniAppDatabases";
import MiniAppChatPanel from "../components/mini-apps/MiniAppChatPanel";

const POLL_INTERVAL_MS = 2000;

const VISIBILITY_LABELS: Record<MiniApp["visibility_tier"], string> = {
  public: "Công khai",
  need_auth: "Cần đăng nhập",
  private: "Riêng tư",
};

export function MiniAppHostPage() {
  const { appId } = useParams<{ appId: string }>();

  const appQuery = useQuery<MiniApp, Error>({
    queryKey: ["mini-app", appId],
    queryFn: () => getMiniApp(appId as string),
    enabled: Boolean(appId),
    refetchInterval: (q) => {
      const status = q.state.data?.build_status;
      return status === "pending" || status === "building" ? POLL_INTERVAL_MS : false;
    },
  });

  const app = appQuery.data;
  const isReady = app?.build_status === "ready";

  const dbQuery = useMiniAppDatabases();
  const boundDb = app?.database_id
    ? (dbQuery.data ?? []).find((d) => d.id === app.database_id)
    : undefined;

  const tokenQuery = useQuery<{ token: string }, Error>({
    queryKey: ["mini-app-token", appId],
    queryFn: () => getScopedToken(appId as string),
    enabled: Boolean(appId) && isReady,
  });

  const { show } = useToast();
  // Local-only visibility override (mock control; not persisted).
  const [visOverride, setVisOverride] = useState<MiniApp["visibility_tier"] | "">("");

  if (appQuery.isLoading) {
    return (
      <div data-testid="vaic-mini-app-host-loading">
        <Skeleton height="32px" width="240px" style={{ marginBottom: "var(--space-3)" }} />
        <Skeleton height="480px" />
      </div>
    );
  }

  if (appQuery.isError) {
    return (
      <ErrorState
        message={appQuery.error?.message ?? "Failed to load Mini-App"}
        retry={
          <Button variant="secondary" onClick={() => appQuery.refetch()}>
            Retry
          </Button>
        }
      />
    );
  }

  if (!app) {
    return <ErrorState message="Mini-App not found" />;
  }

  return (
    <div
      data-testid="vaic-mini-app-host-page"
      style={{ display: "flex", flexDirection: "column", height: "calc(100vh - var(--topbar-h, 64px) - 2 * var(--space-4))", gap: "var(--space-3)" }}
    >
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          gap: "var(--space-3)",
          flexWrap: "wrap",
        }}
      >
        <div style={{ minWidth: 0 }}>
          <h1 className="text-h1" style={{ marginBottom: "var(--space-1)" }}>{app.name}</h1>
          {app.description && (
            <p className="text-body" style={{ color: "var(--color-text-tertiary)" }}>{app.description}</p>
          )}
          {app.database_id && (
            <p className="text-small" style={{ color: "var(--color-text-tertiary)", marginTop: "var(--space-1)" }}>
              Database:{" "}
              <Link to="/database" className="vaic-focusable" style={{ color: "var(--color-primary)" }}>
                {boundDb?.name ?? "View in Database"}
              </Link>
            </p>
          )}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", flexWrap: "wrap", flexShrink: 0 }}>
          <label
            htmlFor="vaic-miniapp-visibility"
            className="text-small"
            style={{ color: "var(--color-text-tertiary)" }}
          >
            Hiển thị
          </label>
          <select
            id="vaic-miniapp-visibility"
            className="vaic-form-input vaic-focusable"
            style={{ width: "auto", padding: "6px 10px" }}
            value={visOverride || app.visibility_tier}
            onChange={(e) => {
              const v = e.target.value as MiniApp["visibility_tier"];
              setVisOverride(v);
              show(`Đã đặt hiển thị: ${VISIBILITY_LABELS[v]} (demo)`);
            }}
          >
            <option value="public">{VISIBILITY_LABELS.public}</option>
            <option value="need_auth">{VISIBILITY_LABELS.need_auth}</option>
            <option value="private">{VISIBILITY_LABELS.private}</option>
          </select>
          <Button
            variant="secondary"
            disabled={!isReady || !tokenQuery.data}
            onClick={() => {
              const token = tokenQuery.data?.token;
              if (!appId || !token) return;
              const apiBase = import.meta.env.VITE_API_BASE ?? "";
              const src = `${apiBase}/mini-app-runtime/${appId}/index.html`;
              const hash = new URLSearchParams({
                appId,
                token,
                apiBase,
                cb: app.updated_at,
              }).toString();
              window.open(`${src}#${hash}`, "_blank", "noopener");
            }}
          >
            Mở tab mới ↗
          </Button>
        </div>
      </header>

      <div
        style={{ flex: 1, minHeight: 0, display: "grid", gridTemplateColumns: "minmax(320px, 2fr) 3fr", gap: "var(--space-3)" }}
      >
        <div style={{ minHeight: 0 }}>
          {appId && <MiniAppChatPanel app={app} appId={appId} />}
        </div>

        <div style={{ minHeight: 0, display: "flex", flexDirection: "column" }} data-testid="vaic-mini-app-preview">
          {(app.build_status === "pending" || app.build_status === "building") && (
            <Card title="Building your Mini-App…">
              <p className="text-body" style={{ color: "var(--color-text-tertiary)" }}>
                This usually takes a few moments. The preview refreshes automatically.
              </p>
              <Skeleton height="14px" width="60%" style={{ marginTop: "var(--space-3)" }} />
            </Card>
          )}
          {app.build_status === "failed" && (
            <ErrorState
              message="Mini-App build failed"
              detail={app.build_error ?? undefined}
              retry={<Button variant="secondary" onClick={() => appQuery.refetch()}>Retry</Button>}
            />
          )}
          {isReady && tokenQuery.isLoading && <Skeleton height="100%" />}
          {isReady && tokenQuery.isError && (
            <ErrorState
              message={tokenQuery.error?.message ?? "Failed to obtain a session token"}
              retry={<Button variant="secondary" onClick={() => tokenQuery.refetch()}>Retry</Button>}
            />
          )}
          {isReady && tokenQuery.data && appId && (
            <MiniAppIframe app={app} appId={appId} token={tokenQuery.data.token} />
          )}
        </div>
      </div>
    </div>
  );
}

function MiniAppIframe({ app, appId, token }: { app: MiniApp; appId: string; token: string }) {
  const apiBase = import.meta.env.VITE_API_BASE ?? "";
  const src = `${apiBase}/mini-app-runtime/${appId}/index.html`;
  const hash = new URLSearchParams({ appId, token, apiBase, cb: app.updated_at }).toString();

  return (
    <iframe
      key={app.updated_at}
      title={app.name}
      data-testid="vaic-mini-app-host-iframe"
      src={`${src}#${hash}`}
      // CRITICAL: allow-scripts + allow-forms only — never allow-same-origin.
      // The scoped token in the URL hash is the sole credential the iframe
      // holds; allow-same-origin would let it read the parent's localStorage
      // (and thus the platform auth token).
      sandbox="allow-scripts allow-forms"
      style={{ flex: 1, width: "100%", minHeight: 0, border: "1px solid var(--color-border)", borderRadius: "var(--radius-control)" }}
    />
  );
}

export default MiniAppHostPage;
