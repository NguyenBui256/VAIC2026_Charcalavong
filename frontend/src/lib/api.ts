/* Story 1.8 — API fetch wrapper that injects JWT + tenant headers.
 * All TanStack Query hooks use this via `apiFetch`.
 */

import { getStoredToken, getStoredUser, clearSession } from "./auth";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

export class ApiError extends Error {
  status: number;
  code: string;
  constructor(message: string, status: number, code: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

/** Build default headers including JWT if present. */
export function authHeaders(): Record<string, string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  const token = getStoredToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const user = getStoredUser();
  if (user) {
    headers["X-Tenant-Id"] = user.tenant_id;
    if (user.department_id) {
      headers["X-Department-Id"] = user.department_id;
    }
  }
  return headers;
}

/** Typed fetch wrapper. On 401, clears session and redirects to /login. */
export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const headers = { ...authHeaders(), ...(init?.headers ?? {}) };
  const resp = await fetch(`${API_BASE}${path}`, { ...init, headers });

  if (resp.status === 401) {
    clearSession();
    if (typeof window !== "undefined" && window.location.pathname !== "/login") {
      window.location.href = "/login";
    }
    throw new ApiError("Authentication required", 401, "UNAUTHENTICATED");
  }

  const body = await resp.json();

  if (!resp.ok) {
    const msg = body?.error?.message ?? "API request failed";
    const code = body?.error?.code ?? "UNKNOWN";
    throw new ApiError(msg, resp.status, code);
  }

  // Unwrap {data, error, meta} envelope.
  return (body?.data ?? body) as T;
}
