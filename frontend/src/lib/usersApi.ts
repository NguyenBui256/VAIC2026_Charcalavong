/* 3D — tenant users list for the node approver picker.
 * Reuses the existing GET /auth/users (list_tenant_users, RLS-scoped). */

import { apiFetch } from "./api";

export interface TenantUser {
  id: string;
  email: string;
  department_id: string | null;
  role: string;
}

export function listUsers(): Promise<TenantUser[]> {
  return apiFetch<TenantUser[]>("/auth/users");
}
