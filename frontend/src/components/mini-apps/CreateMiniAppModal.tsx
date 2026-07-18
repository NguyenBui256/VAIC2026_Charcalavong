/* Create Mini-App modal. Primary path: pick an existing Database (sends
 * database_id; server copies its schema). Fallback: description + expected
 * output (LLM emission). Visibility tier + whitelist as before. */
import { useState, type FormEvent } from "react";
import { Button, Card, FormField, useToast } from "../ui";
import { useMiniAppDatabases } from "../../hooks/useMiniAppDatabases";
import { createMiniApp, type CreateMiniAppInput, type MiniApp } from "../../lib/miniAppsApi";
import { useMutation, useQueryClient } from "@tanstack/react-query";

type Tier = MiniApp["visibility_tier"];

export interface CreateMiniAppModalProps {
  onClose: () => void;
}

export default function CreateMiniAppModal({ onClose }: CreateMiniAppModalProps) {
  const qc = useQueryClient();
  const { show } = useToast();
  const dbQuery = useMiniAppDatabases();
  const databases = dbQuery.data ?? [];

  const [name, setName] = useState("");
  const [databaseId, setDatabaseId] = useState<string>("");
  const [description, setDescription] = useState("");
  const [expectedOutput, setExpectedOutput] = useState("");
  const [tier, setTier] = useState<Tier>("public");
  const [whitelist, setWhitelist] = useState("");

  const create = useMutation<MiniApp, Error, CreateMiniAppInput>({
    mutationFn: createMiniApp,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["mini-apps"] });
      show("Mini-App created");
      onClose();
    },
    onError: (err) => show(err.message || "Failed to create Mini-App", "error"),
  });

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!name.trim()) { show("Name is required", "error"); return; }
    if (!databaseId && !expectedOutput.trim()) {
      show("Pick a Database or provide an expected output", "error"); return;
    }
    const wl = tier === "private" ? whitelist.split(",").map((s) => s.trim()).filter(Boolean) : [];
    const input: CreateMiniAppInput = {
      name,
      description: description || undefined,
      visibility_tier: tier,
      whitelist_user_ids: wl,
    };
    if (databaseId) input.database_id = databaseId;
    else input.expected_output = expectedOutput;
    create.mutate(input);
  }

  return (
    <div
      role="dialog" aria-modal="true" aria-label="Create Mini-App"
      style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)",
        display: "flex", alignItems: "center", justifyContent: "center", zIndex: 50, padding: "var(--space-4)",
      }}
      onClick={onClose}
    >
      <div style={{ width: "min(560px, 100%)", maxHeight: "90vh", overflowY: "auto" }} onClick={(e) => e.stopPropagation()}>
        <Card title="Create Mini-App" headerAction={<Button variant="secondary" onClick={onClose}>Close</Button>}>
          <form onSubmit={handleSubmit} data-testid="vaic-create-mini-app-form">
            <FormField
              label="Name" required value={name}
              onChange={(e) => setName(e.target.value)}
              validate={(v) => (v.trim() ? null : "Name is required")}
            />

            <div className="vaic-form-field">
              <label className="vaic-form-label" htmlFor="vaic-mini-app-database">Database</label>
              <select
                id="vaic-mini-app-database" className="vaic-form-input vaic-focusable"
                value={databaseId} onChange={(e) => setDatabaseId(e.target.value)}
              >
                <option value="">— None (describe below) —</option>
                {databases.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
              <p className="text-small" style={{ color: "var(--color-text-tertiary)" }}>
                Pick a Database to reuse its schema, or leave blank and describe the app below.
              </p>
            </div>

            {!databaseId && (
              <>
                <div className="vaic-form-field">
                  <label className="vaic-form-label" htmlFor="vaic-mini-app-description">Description</label>
                  <textarea
                    id="vaic-mini-app-description" rows={2} className="vaic-form-input vaic-focusable"
                    value={description} onChange={(e) => setDescription(e.target.value)}
                  />
                </div>
                <div className="vaic-form-field">
                  <label className="vaic-form-label" htmlFor="vaic-mini-app-expected-output">Expected output</label>
                  <textarea
                    id="vaic-mini-app-expected-output" rows={3} className="vaic-form-input vaic-focusable"
                    value={expectedOutput} onChange={(e) => setExpectedOutput(e.target.value)}
                  />
                </div>
              </>
            )}

            <div className="vaic-form-field">
              <label className="vaic-form-label" htmlFor="vaic-mini-app-tier">Visibility tier</label>
              <select
                id="vaic-mini-app-tier" className="vaic-form-input vaic-focusable"
                value={tier} onChange={(e) => setTier(e.target.value as Tier)}
              >
                <option value="public">Public</option>
                <option value="need_auth">Need Auth</option>
                <option value="private">Private</option>
              </select>
            </div>

            {tier === "private" && (
              <FormField
                label="Whitelist user ids"
                helperText="Comma-separated user ids allowed to access this Mini-App"
                value={whitelist} onChange={(e) => setWhitelist(e.target.value)}
              />
            )}

            <div style={{ display: "flex", gap: "var(--space-2)", marginTop: "var(--space-3)" }}>
              <Button variant="primary" type="submit" disabled={create.isPending}>
                {create.isPending ? "Creating…" : "Create Mini-App"}
              </Button>
              <Button variant="secondary" type="button" onClick={onClose}>Cancel</Button>
            </div>
          </form>
        </Card>
      </div>
    </div>
  );
}
