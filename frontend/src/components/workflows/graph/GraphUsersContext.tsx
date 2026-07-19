/* Frontend-only: makes the tenant user roster available to custom React Flow
 * nodes (AgentNode) so approver ids resolve to emails/initials WITHOUT baking
 * stale user data into node state. */

import { createContext, useContext, useMemo, type ReactNode } from "react";
import type { TenantUser } from "../../../lib/usersApi";

const GraphUsersCtx = createContext<Map<string, TenantUser>>(new Map());

export function GraphUsersProvider({
  users,
  children,
}: {
  users: TenantUser[];
  children: ReactNode;
}) {
  const map = useMemo(
    () => new Map(users.map((u) => [u.id, u])),
    [users],
  );
  return <GraphUsersCtx.Provider value={map}>{children}</GraphUsersCtx.Provider>;
}

export function useGraphUsers(): Map<string, TenantUser> {
  return useContext(GraphUsersCtx);
}
