"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { BootstrapMeta, Session } from "@/lib/types";

interface SessionState {
  session: Session | null;
  meta: BootstrapMeta | null;
  loading: boolean;
  error: string | null;
  has: (permission: string) => boolean;
  reload: () => Promise<void>;
  signOut: () => Promise<void>;
}

const SessionContext = createContext<SessionState | null>(null);

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [meta, setMeta] = useState<BootstrapMeta | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [current, bootstrap] = await Promise.all([
        api.get<Session>("/api/v1/auth/me"),
        api.get<BootstrapMeta>("/api/v1/meta/bootstrap"),
      ]);
      setSession(current);
      setMeta(bootstrap);
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : "Unable to load your session.";
      setError(message);
      setSession(null);
      // Only redirect on authentication errors (401), not network errors
      if (
        typeof window !== "undefined" &&
        !window.location.pathname.startsWith("/login") &&
        err instanceof ApiError &&
        err.status === 401
      ) {
        window.location.href = "/login";
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const signOut = useCallback(async () => {
    try {
      await api.post("/api/v1/auth/logout");
    } finally {
      window.location.href = "/login";
    }
  }, []);

  const value = useMemo<SessionState>(
    () => ({
      session,
      meta,
      loading,
      error,
      has: (permission: string) => Boolean(session?.user.permissions.includes(permission)),
      reload: load,
      signOut,
    }),
    [session, meta, loading, error, load, signOut],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionState {
  const context = useContext(SessionContext);
  if (!context) throw new Error("useSession must be used inside SessionProvider");
  return context;
}
