"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

import { api } from "@/lib/api";
import type { UserSession } from "@/lib/types";

type AuthContextValue = {
  token: string | null;
  user: UserSession | null;
  ready: boolean;
  eventId: number;
  setEventId: (value: number) => void;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function defaultRouteForRole(role: string) {
  if (role === "evaluador") {
    return "/evaluator";
  }
  if (role === "estudiante") {
    return "/student";
  }
  return "/dashboard";
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<UserSession | null>(null);
  const [ready, setReady] = useState(false);
  const [eventId, setEventIdState] = useState<number>(() => {
    if (typeof window === "undefined") {
      return 1;
    }
    return Number(window.localStorage.getItem("ecoe-event-id") ?? "1");
  });
  const router = useRouter();
  const pathname = usePathname();

  const setEventId = useCallback((value: number) => {
    setEventIdState(value);
    if (typeof window !== "undefined") {
      window.localStorage.setItem("ecoe-event-id", String(value));
    }
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    setReady(true);
    void api.logout().catch(() => undefined);
    router.push("/login");
  }, [router]);

  const login = useCallback(async (email: string, password: string) => {
    const response = await api.login(email, password);
    const authUser = response.user as UserSession;
    setToken("cookie-session");
    setUser(authUser);
    setReady(true);
    router.push(defaultRouteForRole(authUser.role));
  }, [router]);

  useEffect(() => {
    let active = true;

    api
      .me()
      .then((response) => {
        if (!active) {
          return;
        }
        setToken("cookie-session");
        setUser(response as UserSession);
        setReady(true);
      })
      .catch(() => {
        if (!active) {
          return;
        }
        setToken(null);
        setUser(null);
        setReady(true);
        if (pathname !== "/login") {
          router.replace("/login");
        }
      });

    return () => {
      active = false;
    };
  }, [pathname, router]);

  const value = useMemo(
    () => ({ token, user, ready, eventId, setEventId, login, logout }),
    [eventId, login, logout, ready, setEventId, token, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth debe usarse dentro de AuthProvider");
  }
  return context;
}
