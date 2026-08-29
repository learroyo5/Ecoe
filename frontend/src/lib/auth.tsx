"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { api } from "@/lib/api";
import { defaultRouteForRole } from "@/lib/routes";
import type { DashboardSummary, ECOEEvent, UserSession } from "@/lib/types";

type ECOEContextValue = {
  ecoeList: ECOEEvent[];
  ecoeEvent: ECOEEvent | null;
  dashboard: DashboardSummary | null;
  authenticated: boolean;
  user: UserSession | null;
  eventRoles: string[];
  /** true once the effective ECOE roles for the active event have been
   *  fetched at least once. Guards must wait for this before redirecting,
   *  so a multi-role account is not bounced on the initial empty `[]`. */
  eventRolesLoaded: boolean;
  ready: boolean;
  eventId: number;
  loading: boolean;
  /** Last failure loading the ECOE list/dashboard, surfaced by AppShell. */
  loadError: string | null;
  /** true when the account authenticated fine but has no ECOE it can reach
   *  (no ECOEPermission / StaffAssignment / enrollment). AppShell renders a
   *  dedicated empty-state instead of a technical error. */
  noAccessibleEvents: boolean;
  setEventId: (value: number) => void;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  refreshECOE: () => Promise<void>;
};

const ECOEContext = createContext<ECOEContextValue | null>(null);

export function ECOEProvider({ children }: { children: React.ReactNode }) {
  const [authenticated, setAuthenticated] = useState(false);
  const [user, setUser] = useState<UserSession | null>(null);
  const [eventRoles, setEventRoles] = useState<string[]>([]);
  const [eventRolesLoaded, setEventRolesLoaded] = useState(false);
  const [ready, setReady] = useState(false);
  const [loading, setLoading] = useState(false);
  const [ecoeList, setECOEList] = useState<ECOEEvent[]>([]);
  const [ecoeEvent, setECOEEvent] = useState<ECOEEvent | null>(null);
  const [dashboard, setDashboard] = useState<DashboardSummary | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [noAccessibleEvents, setNoAccessibleEvents] = useState(false);

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

  const loadECOEList = useCallback(async (): Promise<ECOEEvent[] | null> => {
    if (!authenticated) return null;
    try {
      const list = await api.listECOE();
      setECOEList(list);
      setNoAccessibleEvents(list.length === 0);
      // Do NOT clear loadError here: loadECOEData runs right after this in
      // refreshECOE, and clearing on this call's success would hide a
      // failure from loadECOEList once loadECOEData succeeds. Both callers
      // share one error slot, cleared once at the top of refreshECOE.
      const exists = list.some((e) => e.id === eventId);
      if (!exists && list.length > 0) {
        setEventId(list[0].id);
      }
      return list;
    } catch (err) {
      setLoadError(
        err instanceof Error
          ? `No se pudo cargar la lista de ECOE: ${err.message}`
          : "No se pudo cargar la lista de ECOE.",
      );
      return null;
    }
  }, [authenticated, eventId, setEventId]);

  const loadECOEData = useCallback(async () => {
    if (!authenticated || !eventId) return;
    setLoading(true);
    setEventRolesLoaded(false);
    try {
      const [event, dash, roleContext] = await Promise.all([
        api.ecoe(eventId),
        api.dashboard(eventId).catch(() => null),
        api.eventRoles(eventId),
      ]);
      setECOEEvent(event);
      setEventRoles(roleContext.roles);
      setEventRolesLoaded(true);
      if (dash) setDashboard(dash);
      // Not cleared here either — see the comment in loadECOEList above.
    } catch (err) {
      setLoadError(
        err instanceof Error
          ? `No se pudo cargar el ECOE activo: ${err.message}`
          : "No se pudo cargar el ECOE activo.",
      );
    } finally {
      setLoading(false);
    }
  }, [authenticated, eventId]);

  const refreshECOE = useCallback(async () => {
    setLoadError(null);
    const list = await loadECOEList();
    // An account with no accessible ECOE would only hit api.ecoe(1) → 403 and
    // surface a technical error. Skip the data load and let AppShell show the
    // empty-state (H-roles-usuario-4 / OPT-10).
    if (list && list.length === 0) return;
    await loadECOEData();
  }, [loadECOEList, loadECOEData]);

  // Auth check on mount
  useEffect(() => {
    let active = true;
    api.me()
      .then((response) => {
        if (!active) return;
        setAuthenticated(true);
        setUser(response as UserSession);
        setReady(true);
      })
      .catch(() => {
        if (!active) return;
        setAuthenticated(false);
        setUser(null);
        setReady(true);
      });
    return () => { active = false; };
  }, []);

  // Load ECOE data when auth/eventId changes
  useEffect(() => {
    if (!ready || !authenticated) return;
    void refreshECOE();
  }, [ready, authenticated, eventId, refreshECOE]);

  const login = useCallback(async (email: string, password: string) => {
    const response = await api.login(email, password);
    const authUser = { id: response.user.id, email: response.user.email, full_name: response.user.full_name, role: response.user.role };
    setAuthenticated(true);
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
    setAuthenticated(false);
    setUser(null);
    setECOEList([]);
    setECOEEvent(null);
    setEventRoles([]);
    setEventRolesLoaded(false);
    setDashboard(null);
    setNoAccessibleEvents(false);
    setReady(true);
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
  }, []);

  const value = useMemo(
    () => ({
      ecoeList, ecoeEvent, dashboard, authenticated, user, eventRoles, eventRolesLoaded, ready, eventId, loading, loadError, noAccessibleEvents,
      setEventId, login, logout, refreshECOE,
    }),
    [ecoeList, ecoeEvent, dashboard, authenticated, user, eventRoles, eventRolesLoaded, ready, eventId, loading, loadError, noAccessibleEvents, setEventId, login, logout, refreshECOE],
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
