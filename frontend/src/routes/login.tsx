/* Story 1.8 — Login page.
 * Accepts email + password, calls POST /auth/login, stores JWT, redirects to /dashboard.
 * Failed login shows inline error in --color-destructive.
 * UX-DR1 layout: centered card on branded backdrop, text-display hero.
 */

import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { login, storeSession } from "../lib/auth";

const pageStyle: React.CSSProperties = {
  minHeight: "100vh",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  background: "var(--color-bg)",
  padding: "var(--space-6)",
};

const cardStyle: React.CSSProperties = {
  width: "100%",
  maxWidth: "400px",
  background: "var(--color-surface)",
  border: "1px solid var(--color-border)",
  borderRadius: "var(--radius-panel)",
  padding: "var(--space-8)",
  boxShadow: "var(--shadow-md)",
};

const wordmarkStyle: React.CSSProperties = {
  fontSize: "var(--text-h3)",
  fontWeight: 800,
  color: "var(--color-primary)",
  letterSpacing: "-0.02em",
  marginBottom: "var(--space-2)",
};

const labelStyle: React.CSSProperties = {
  display: "block",
  fontSize: "var(--text-small)",
  fontWeight: 600,
  color: "var(--color-text-secondary)",
  marginBottom: "var(--space-1)",
};

const inputBaseStyle: React.CSSProperties = {
  width: "100%",
  padding: "var(--space-2) var(--space-3)",
  border: "1px solid var(--color-border-strong)",
  borderRadius: "var(--radius-control)",
  background: "var(--color-surface)",
  color: "var(--color-text)",
  fontSize: "var(--text-body)",
};

const submitStyle: React.CSSProperties = {
  width: "100%",
  padding: "var(--space-2) var(--space-4)",
  border: "none",
  borderRadius: "var(--radius-control)",
  background: "var(--color-primary)",
  color: "var(--color-on-primary)",
  fontSize: "var(--text-body)",
  fontWeight: 600,
};

export default function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const result = await login(email, password);
      storeSession(result.access_token, result.user);
      navigate("/dashboard");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Login failed";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="vaic-login-page" style={pageStyle} data-testid="vaic-login-page">
      <div className="vaic-login-card" style={cardStyle}>
        <div style={wordmarkStyle}>VAIC</div>
        <h1 className="text-display" style={{ marginBottom: "var(--space-2)" }}>
          Welcome back
        </h1>
        <p className="text-small" style={{ color: "var(--color-text-tertiary)", marginBottom: "var(--space-6)" }}>
          Sign in to your VAIC workspace
        </p>

        <form onSubmit={handleSubmit} noValidate>
          <div style={{ marginBottom: "var(--space-4)" }}>
            <label htmlFor="email" style={labelStyle}>
              Email <span style={{ color: "var(--color-destructive)" }}>*</span>
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              placeholder="you@bank.vn"
              style={inputBaseStyle}
              aria-invalid={error ? true : undefined}
            />
          </div>

          <div style={{ marginBottom: "var(--space-4)" }}>
            <label htmlFor="password" style={labelStyle}>
              Password <span style={{ color: "var(--color-destructive)" }}>*</span>
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
              placeholder="••••••••"
              style={inputBaseStyle}
            />
          </div>

          {error && (
            <div
              role="alert"
              data-testid="vaic-login-error"
              style={{
                padding: "var(--space-2) var(--space-3)",
                marginBottom: "var(--space-4)",
                background: "var(--color-destructive-soft)",
                color: "var(--color-destructive)",
                borderRadius: "var(--radius-control)",
                fontSize: "var(--text-small)",
                border: "1px solid var(--color-destructive)",
              }}
            >
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            style={submitStyle}
            data-testid="vaic-login-submit"
          >
            {loading ? "Signing in..." : "Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}
