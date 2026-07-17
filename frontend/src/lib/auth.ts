/* Story 1.8 — Auth utilities: JWT storage, login API call, logout.
 * Uses sessionStorage for hackathon demo simplicity.
 * Backend contract: POST /auth/login {email, password} → {data: {access_token, token_type, user}}.
 */

const TOKEN_KEY = "vaic_access_token";
const USER_KEY = "vaic_user";

export interface AuthUser {
  id: string;
  tenant_id: string;
  department_id: string | null;
  email: string;
  role: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

/** API base — proxied to backend in dev via vite.config.ts. */
const API_BASE = import.meta.env.VITE_API_BASE ?? "";

/** Store JWT + user profile in sessionStorage. */
export function storeSession(token: string, user: AuthUser): void {
  sessionStorage.setItem(TOKEN_KEY, token);
  sessionStorage.setItem(USER_KEY, JSON.stringify(user));
}

/** Clear all auth state from sessionStorage. */
export function clearSession(): void {
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(USER_KEY);
}

/** Read the raw JWT string (or null). */
export function getStoredToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY);
}

/** Read the stored user profile (or null). */
export function getStoredUser(): AuthUser | null {
  const raw = sessionStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

/** Check if a token exists (does not validate expiry client-side). */
export function isAuthenticated(): boolean {
  return getStoredToken() !== null;
}

/** Call POST /auth/login. Throws Error with server message on failure. */
export async function login(email: string, password: string): Promise<LoginResponse> {
  const resp = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  const body = await resp.json();

  if (!resp.ok) {
    const msg = body?.error?.message ?? "Login failed";
    throw new Error(msg);
  }

  // Success envelope: {data: {access_token, token_type, user}, error: null, meta: {}}
  const data = body?.data ?? body;
  return data as LoginResponse;
}

/** Logout — clear local state. Backend uses stateless JWT (no server-side revoke). */
export function logout(): void {
  clearSession();
}
