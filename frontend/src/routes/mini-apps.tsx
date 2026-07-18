/* Story 4.7 — Mini-App catalog page (/mini-apps): list + create (Task 15).
 *
 * Mirrors routes/workflows.tsx structure (TanStack Query, ui primitives,
 * loading/empty/error states) plus an inline create form (mirrors the
 * FormField + useMutation + useToast pattern from IdentityTab.tsx).
 *
 * "View generated code" is deferred — it needs a backend
 * `GET /mini-apps/{id}/source` route that doesn't exist yet (YAGNI).
 */

import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Card,
  EmptyState,
  ErrorState,
  FormField,
  Skeleton,
  StatusPill,
  useToast,
} from "../components/ui";
import type { RunState } from "../lib/icons";
import { semanticIcons, ICON_STROKE_WIDTH } from "../lib/icons";
import {
  createMiniApp,
  listMiniApps,
  type CreateMiniAppInput,
  type MiniApp,
} from "../lib/miniAppsApi";

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

interface CreateFormState {
  name: string;
  description: string;
  expectedOutput: string;
  visibilityTier: MiniApp["visibility_tier"];
  whitelistUserIds: string;
}

const INITIAL_FORM: CreateFormState = {
  name: "",
  description: "",
  expectedOutput: "",
  visibilityTier: "public",
  whitelistUserIds: "",
};

export function MiniAppsPage() {
  const queryClient = useQueryClient();
  const { show } = useToast();

  const query = useQuery<MiniApp[], Error>({
    queryKey: ["mini-apps"],
    queryFn: listMiniApps,
  });

  const apps = query.data ?? [];
  const isLoading = query.isLoading;
  const isError = query.isError;
  const isEmpty = !isLoading && !isError && apps.length === 0;

  const [form, setForm] = useState<CreateFormState>(INITIAL_FORM);

  const create = useMutation<MiniApp, Error, CreateMiniAppInput>({
    mutationFn: createMiniApp,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["mini-apps"] });
      show("Mini-App created");
      setForm(INITIAL_FORM);
    },
    onError: (err) => {
      show(err.message || "Failed to create Mini-App", "error");
    },
  });

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!form.name.trim()) return;

    const whitelist =
      form.visibilityTier === "private"
        ? form.whitelistUserIds
            .split(",")
            .map((id) => id.trim())
            .filter(Boolean)
        : [];

    create.mutate({
      name: form.name,
      description: form.description || undefined,
      expected_output: form.expectedOutput || undefined,
      visibility_tier: form.visibilityTier,
      whitelist_user_ids: whitelist,
    });
  }

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
          description="Create your first Mini-App using the form below."
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
      <header style={{ marginBottom: "var(--space-4)" }}>
        <h1 className="text-h1" style={{ marginBottom: "var(--space-1)" }}>
          Mini-Apps
        </h1>
        <p className="text-body" style={{ color: "var(--color-text-tertiary)" }}>
          Lightweight, LLM-generated data apps scoped to your Tenant.
        </p>
      </header>

      {renderList()}

      <div style={{ marginTop: "var(--space-5)" }}>
        <Card title="Create Mini-App" className="vaic-mini-apps-create-card">
          <form onSubmit={handleSubmit} data-testid="vaic-mini-apps-create-form">
            <FormField
              label="Name"
              required
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              validate={(v) => (v.trim() ? null : "Name is required")}
            />

            <div className="vaic-form-field">
              <label htmlFor="vaic-mini-app-description" className="vaic-form-label">
                Description
              </label>
              <textarea
                id="vaic-mini-app-description"
                rows={3}
                className="vaic-form-input vaic-focusable"
                value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              />
            </div>

            <div className="vaic-form-field">
              <label htmlFor="vaic-mini-app-expected-output" className="vaic-form-label">
                Expected output
              </label>
              <textarea
                id="vaic-mini-app-expected-output"
                rows={3}
                className="vaic-form-input vaic-focusable"
                value={form.expectedOutput}
                onChange={(e) => setForm((f) => ({ ...f, expectedOutput: e.target.value }))}
              />
            </div>

            <div className="vaic-form-field">
              <label htmlFor="vaic-mini-app-tier" className="vaic-form-label">
                Visibility tier
              </label>
              <select
                id="vaic-mini-app-tier"
                className="vaic-form-input vaic-focusable"
                value={form.visibilityTier}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    visibilityTier: e.target.value as MiniApp["visibility_tier"],
                  }))
                }
              >
                <option value="public">Public</option>
                <option value="need_auth">Need Auth</option>
                <option value="private">Private</option>
              </select>
            </div>

            {form.visibilityTier === "private" && (
              <FormField
                label="Whitelist user ids"
                helperText="Comma-separated user ids allowed to access this Mini-App"
                value={form.whitelistUserIds}
                onChange={(e) => setForm((f) => ({ ...f, whitelistUserIds: e.target.value }))}
              />
            )}

            <Button variant="primary" type="submit" disabled={create.isPending}>
              {create.isPending ? "Creating…" : "Create Mini-App"}
            </Button>
          </form>
        </Card>
      </div>
    </div>
  );
}

export default MiniAppsPage;
