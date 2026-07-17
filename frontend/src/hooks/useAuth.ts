/* Story 1.8 — Auth state hook. Provides reactive auth state across the app. */

import { useState, useEffect, useCallback } from "react";
import {
  type AuthUser,
  getStoredToken,
  getStoredUser,
  clearSession,
} from "../lib/auth";

export interface AuthState {
  user: AuthUser | null;
  token: string | null;
  isAuthenticated: boolean;
  logout: () => void;
}

export function useAuth(): AuthState {
  const [user, setUser] = useState<AuthUser | null>(() => getStoredUser());
  const [token, setToken] = useState<string | null>(() => getStoredToken());

  // Sync if another tab changes sessionStorage.
  useEffect(() => {
    function onStorage(e: StorageEvent) {
      if (e.key === "vaic_access_token" || e.key === "vaic_user") {
        setUser(getStoredUser());
        setToken(getStoredToken());
      }
    }
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const logout = useCallback(() => {
    clearSession();
    setUser(null);
    setToken(null);
  }, []);

  return {
    user,
    token,
    isAuthenticated: token !== null,
    logout,
  };
}
