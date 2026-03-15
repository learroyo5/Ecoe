"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

import { api } from "@/lib/api";
import type { UserSession } from "@/lib/types";

type AuthContextValue = {
  token: string | null;
  user: UserSession | null;
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
  const [token, setToken] = useState<string | null>(() =>
    typeof window === "undefined" ? null : window.localStorage.getItem("ecoe-token"),
  );
  const [user, setUser] = useState<UserSession | null>(() => {
    if (typeof window === "undefined") {
      return null;
    }
    const storedUser = window.localStorage.getItem("ecoe-user");
    return storedUser ? (JSON.parse(storedUser) as UserSession) : null;
  });
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
    window.localStorage.removeItem("ecoe-token");
    window.localStorage.removeItem("ecoe-user");
    router.push("/login");
  }, [router]);

  const login = useCallback(async (email: string, password: string) => {
    const response = await api.login(email, password);
    const authToken = response.access_token;
    const authUser = response.user as UserSession;
    setToken(authToken);
    setUser(authUser);
    window.localStorage.setItem("ecoe-token", authToken);
    window.localStorage.setItem("ecoe-user", JSON.stringify(authUser));
    router.push(defaultRouteForRole(authUser.role));
  }, [router]);

  useEffect(() => {
    if (!token || user || pathname === "/login") {
      return;
    }
    api
      .me(token)
      .then((response) => {
        setUser(response as UserSession);
        window.localStorage.setItem("ecoe-user", JSON.stringify(response));
      })
      .catch(() => {
        logout();
      });
  }, [logout, pathname, token, user]);

  const value = useMemo(
    () => ({ token, user, eventId, setEventId, login, logout }),
    [eventId, login, logout, setEventId, token, user],
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
