type Column<T> = {
  key: keyof T | string;
  label: string;
  render?: (row: T) => React.ReactNode;
};

export function DataTable<T>({
  columns,
  rows,
}: {
  columns: Array<Column<T>>;
  rows: T[];
}) {
  return (
    <div className="panel-card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-slate-900 text-white">
            <tr>
              {columns.map((column) => (
                <th key={String(column.key)} className="px-4 py-3 font-semibold">
                  {column.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
            <tr
              key={String((row as { id?: number | string }).id ?? index)}
              className="border-b border-slate-200/70"
            >
                {columns.map((column) => (
                  <td key={String(column.key)} className="px-4 py-3 align-top">
                    {column.render
                      ? column.render(row)
                      : String((row as Record<string, unknown>)[column.key as string] ?? "")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
