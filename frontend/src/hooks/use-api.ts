"use client";

import { useEffect, useRef, useState } from "react";

export function useApi<T>(fetcher: () => Promise<T>, dependencies: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const fetcherRef = useRef(fetcher);
  const dependenciesKey = JSON.stringify(dependencies);

  fetcherRef.current = fetcher;

  useEffect(() => {
    let active = true;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const response = await fetcherRef.current();
        if (active) {
          setData(response);
        }
      } catch (err) {
        if (active) {
          setError(err instanceof Error ? err.message : "Error inesperado");
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    void load();

    return () => {
      active = false;
    };
  }, [dependenciesKey]);

  return { data, loading, error, setData };
}
