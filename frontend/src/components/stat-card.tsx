export function StatCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: string | number;
  hint: string;
}) {
  return (
    <div className="panel-card">
      <p className="text-sm text-slate-500">{label}</p>
      <p className="mt-3 text-4xl font-semibold text-slate-900">{value}</p>
      <p className="mt-2 text-sm text-slate-600">{hint}</p>
    </div>
  );
}
