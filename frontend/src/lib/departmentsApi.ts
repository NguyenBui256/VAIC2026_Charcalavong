/* Story 2.2 — Departments API layer.
 *
 * Used by the Agent list Department filter dropdown and the Identity tab's
 * Department select. Backend endpoint TBD (open question in story 2.2 —
 * develop against this typed wrapper now, wire to the live endpoint when
 * available; the shape mirrors the `departments` table used by seed data).
 */

import { apiFetch } from "./api";

export interface Department {
  id: string;
  name: string;
}

export function listDepartments(): Promise<Department[]> {
  return apiFetch<Department[]>("/departments");
}
