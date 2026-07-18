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

const toggleStyle: React.CSSProperties = {
  position: "absolute",
  top: "50%",
  right: "var(--space-2)",
  transform: "translateY(-50%)",
  border: "none",
  background: "transparent",
  color: "var(--color-text-secondary)",
  cursor: "pointer",
  padding: "var(--space-1)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  lineHeight: 0,
};

function EyeIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function EyeOffIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c6.5 0 10 8 10 8a18.5 18.5 0 0 1-2.16 3.19M6.61 6.61A18.5 18.5 0 0 0 2 12s3.5 8 10 8a9.12 9.12 0 0 0 5.39-1.61" />
      <path d="M14.12 14.12a3 3 0 1 1-4.24-4.24" />
      <line x1="2" y1="2" x2="22" y2="22" />
    </svg>
  );
}

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
  const [showPassword, setShowPassword] = useState(false);
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
            <div style={{ position: "relative" }}>
              <input
                id="password"
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
                placeholder="••••••••"
                style={{ ...inputBaseStyle, paddingRight: "var(--space-10)" }}
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                aria-label={showPassword ? "Hide password" : "Show password"}
                aria-pressed={showPassword}
                data-testid="vaic-login-toggle-password"
                style={toggleStyle}
              >
                {showPassword ? <EyeOffIcon /> : <EyeIcon />}
              </button>
            </div>
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
