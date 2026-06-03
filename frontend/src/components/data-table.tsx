"use client";

import { useCallback, useMemo, useState } from "react";

type Column<T> = {
  key: string;
  label: string;
  render?: (row: T) => React.ReactNode;
  sortable?: boolean;
};

type PaginatedData = {
  items?: unknown[];
  total?: number;
  page?: number;
  page_size?: number;
  pages?: number;
};

export function DataTable<T>({
  columns,
  rows,
  searchPlaceholder = "Buscar...",
  searchKeys,
  paginated,
  onPageChange,
}: {
  columns: Array<Column<T>>;
  rows: T[] | PaginatedData;
  searchPlaceholder?: string;
  searchKeys?: string[];
  paginated?: boolean;
  onPageChange?: (page: number) => void;
}) {
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  // Unwrap paginated data
  const isPaginated = paginated && "items" in rows && Array.isArray((rows as PaginatedData).items);
  const items: T[] = isPaginated
    ? ((rows as PaginatedData).items as T[])
    : (rows as T[]);
  const pagination = isPaginated ? (rows as PaginatedData) : null;

  // Filter by search
  const filtered = useMemo(() => {
    if (!search.trim() || !searchKeys?.length) return items;
    const term = search.toLowerCase();
    return items.filter((row) =>
      searchKeys.some((key) => {
        const val = (row as Record<string, unknown>)[key];
        return String(val ?? "").toLowerCase().includes(term);
      })
    );
  }, [items, search, searchKeys]);

  // Sort
  const sorted = useMemo(() => {
    if (!sortKey) return filtered;
    return [...filtered].sort((a, b) => {
      const aVal = String((a as Record<string, unknown>)[sortKey] ?? "");
      const bVal = String((b as Record<string, unknown>)[sortKey] ?? "");
      const cmp = aVal.localeCompare(bVal, "es", { numeric: true });
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [filtered, sortKey, sortDir]);

  const handleSort = useCallback((key: string) => {
    setSortKey((prev) => {
      if (prev === key) {
        setSortDir((d) => (d === "asc" ? "desc" : "asc"));
        return key;
      }
      setSortDir("asc");
      return key;
    });
  }, []);

  return (
    <div className="space-y-3">
      {/* Search + pagination info */}
      <div className="flex flex-wrap items-center gap-3">
        {searchKeys?.length ? (
          <div className="relative flex-1 max-w-sm">
            <input
              type="text"
              placeholder={searchPlaceholder}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9"
            />
            <svg className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
        ) : null}
        <p className="text-sm text-slate-500">
          {search.trim() ? `${sorted.length} de ${items.length} resultados` : `${items.length} registros`}
        </p>
      </div>

      {/* Table */}
      <div className="evaluation-table">
        <div className="overflow-x-auto">
          <table>
            <thead>
              <tr>
                {columns.map((col) => {
                  const canSort = col.sortable !== false;
                  const isActive = sortKey === col.key;
                  return (
                    <th
                      key={col.key}
                      className={canSort ? "cursor-pointer select-none hover:bg-slate-100" : ""}
                      onClick={() => canSort && handleSort(col.key)}
                    >
                      <span className="inline-flex items-center gap-1">
                        {col.label}
                        {canSort && isActive ? (
                          <span className="text-xs">{sortDir === "asc" ? "▲" : "▼"}</span>
                        ) : canSort ? (
                          <span className="text-xs text-slate-300">⇅</span>
                        ) : null}
                      </span>
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {sorted.length === 0 ? (
                <tr>
                  <td colSpan={columns.length} className="py-8 text-center text-slate-400">
                    {search.trim() ? "Sin resultados para esta búsqueda" : "Sin registros"}
                  </td>
                </tr>
              ) : (
                sorted.map((row, index) => (
                  <tr key={String((row as { id?: number | string }).id ?? index)} className="transition">
                    {columns.map((col) => (
                      <td key={col.key}>
                        {col.render
                          ? col.render(row)
                          : String((row as Record<string, unknown>)[col.key] ?? "")}
                      </td>
                    ))}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pagination controls */}
      {pagination && (pagination.pages ?? 1) > 1 ? (
        <div className="flex items-center justify-between text-sm text-slate-600">
          <span>
            Página {pagination.page} de {pagination.pages} ({pagination.total} total)
          </span>
          <div className="flex gap-2">
            <button
              className="btn-secondary text-xs"
              disabled={!pagination.page || pagination.page <= 1}
              onClick={() => onPageChange?.((pagination.page ?? 1) - 1)}
            >
              ← Anterior
            </button>
            <button
              className="btn-secondary text-xs"
              disabled={!pagination.page || pagination.page >= (pagination.pages ?? 1)}
              onClick={() => onPageChange?.((pagination.page ?? 1) + 1)}
            >
              Siguiente →
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
