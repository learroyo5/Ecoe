"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { api } from "@/lib/api";
import type { DashboardSummary, ECOEEvent, UserSession } from "@/lib/types";

type ECOEContextValue = {
  ecoeList: ECOEEvent[];
  ecoeEvent: ECOEEvent | null;
  dashboard: DashboardSummary | null;
  token: string | null;
  user: UserSession | null;
  ready: boolean;
  eventId: number;
  loading: boolean;
  setEventId: (value: number) => void;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  refreshECOE: () => Promise<void>;
};

const ECOEContext = createContext<ECOEContextValue | null>(null);

function defaultRouteForRole(role: string) {
  if (role === "evaluador") return "/evaluator";
  if (role === "estudiante") return "/student";
  return "/dashboard";
}

export function ECOEProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<UserSession | null>(null);
  const [ready, setReady] = useState(false);
  const [loading, setLoading] = useState(false);
  const [ecoeList, setECOEList] = useState<ECOEEvent[]>([]);
  const [ecoeEvent, setECOEEvent] = useState<ECOEEvent | null>(null);
  const [dashboard, setDashboard] = useState<DashboardSummary | null>(null);

  const [eventId, setEventIdState] = useState<number>(() => {
    if (typeof window === "undefined") return 1;
    return Number(window.localStorage.getItem("ecoe-event-id") ?? "1");
  });

  const setEventId = useCallback((value: number) => {
    setEventIdState(value);
    if (typeof window !== "undefined") {
      window.localStorage.setItem("ecoe-event-id", String(value));
    }
  }, []);

  const loadECOEList = useCallback(async () => {
    if (!token) return;
    try {
      const list = await api.listECOE(token);
      setECOEList(list);
      const exists = list.some((e) => e.id === eventId);
      if (!exists && list.length > 0) {
        setEventId(list[0].id);
      }
    } catch {
      // Silently fail — auth will handle redirect
    }
  }, [token, eventId, setEventId]);

  const loadECOEData = useCallback(async () => {
    if (!token || !eventId) return;
    setLoading(true);
    try {
      const [event, dash] = await Promise.all([
        api.ecoe(eventId, token),
        api.dashboard(eventId, token).catch(() => null),
      ]);
      setECOEEvent(event);
      if (dash) setDashboard(dash);
    } catch {
      // Silently fail
    } finally {
      setLoading(false);
    }
  }, [token, eventId]);

  const refreshECOE = useCallback(async () => {
    await loadECOEList();
    await loadECOEData();
  }, [loadECOEList, loadECOEData]);

  // Auth check on mount
  useEffect(() => {
    let active = true;
    api.me()
      .then((response) => {
        if (!active) return;
        setToken("cookie-session");
        setUser(response as UserSession);
        setReady(true);
      })
      .catch(() => {
        if (!active) return;
        setToken(null);
        setUser(null);
        setReady(true);
      });
    return () => { active = false; };
  }, []);

  // Load ECOE data when token/eventId changes
  useEffect(() => {
    if (!ready || !token) return;
    void refreshECOE();
  }, [ready, token, eventId, refreshECOE]);

  const login = useCallback(async (email: string, password: string) => {
    const response = await api.login(email, password);
    const authUser = { id: response.user.id, email: response.user.email, full_name: response.user.full_name, role: response.user.role };
    setToken("cookie-session");
    setUser(authUser);
    setReady(true);
    if (typeof window !== "undefined") {
      const targetPath = defaultRouteForRole(authUser.role);
      window.location.href = targetPath;
    }
  }, []);

  const logout = useCallback(async () => {
    // Must await the API call so the cookie is deleted BEFORE redirecting
    try {
      await api.logout();
    } catch {
      // Even if the API fails, clear local state and redirect
    }
    setToken(null);
    setUser(null);
    setECOEList([]);
    setECOEEvent(null);
    setDashboard(null);
    setReady(true);
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
  }, []);

  const value = useMemo(
    () => ({
      ecoeList, ecoeEvent, dashboard, token, user, ready, eventId, loading,
      setEventId, login, logout, refreshECOE,
    }),
    [ecoeList, ecoeEvent, dashboard, token, user, ready, eventId, loading, setEventId, login, logout, refreshECOE],
  );

  return <ECOEContext.Provider value={value}>{children}</ECOEContext.Provider>;
}

export function useECOE() {
  const context = useContext(ECOEContext);
  if (!context) {
    throw new Error("useECOE debe usarse dentro de ECOEProvider");
  }
  return context;
}
