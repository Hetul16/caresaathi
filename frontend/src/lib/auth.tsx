"use client";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, refreshSession, setAccessToken, setSessionLostHandler } from "./api";
import type { Lang } from "./types";

export interface User { id: string; display_name: string; email: string | null; phone: string | null; preferred_language: Lang }
interface AuthResponse { access_token: string; user: User }

type Status = "loading" | "anon" | "authed";

interface AuthCtx {
  status: Status;
  user: User | null;
  login: (identifier: string, password: string) => Promise<void>;
  register: (v: { display_name: string; email?: string; phone?: string; password: string; preferred_language: Lang }) => Promise<void>;
  logout: () => Promise<void>;
}

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status>("loading");
  const [user, setUser] = useState<User | null>(null);

  const adopt = useCallback((r: AuthResponse) => {
    setAccessToken(r.access_token);
    setUser(r.user);
    setStatus("authed");
  }, []);

  const drop = useCallback(() => {
    setAccessToken(null);
    setUser(null);
    setStatus("anon");
  }, []);

  useEffect(() => {
    setSessionLostHandler(drop);
    let alive = true;
    (async () => {
      // On load, trade the refresh cookie for an access token, then fetch the profile.
      if (await refreshSession()) {
        try {
          const me = await api<User>("/auth/me");
          if (alive) { setUser(me); setStatus("authed"); }
          return;
        } catch { /* fall through */ }
      }
      if (alive) drop();
    })();
    return () => { alive = false; setSessionLostHandler(null); };
  }, [drop]);

  const value = useMemo<AuthCtx>(() => ({
    status, user,
    login: async (identifier, password) => adopt(await api<AuthResponse>("/auth/login", { method: "POST", json: { identifier, password } })),
    register: async (v) => adopt(await api<AuthResponse>("/auth/register", { method: "POST", json: v })),
    logout: async () => { try { await api("/auth/logout", { method: "POST" }); } finally { drop(); } },
  }), [status, user, adopt, drop]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useAuth must be used inside AuthProvider");
  return c;
}
