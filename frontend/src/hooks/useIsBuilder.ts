// src/hooks/useIsBuilder.ts — pool management is builder-only (spec §5).
import { useAuth } from "./useAuth";

export function useIsBuilder(): boolean {
  const { user } = useAuth();
  return user?.role === "builder";
}
