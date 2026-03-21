export function SectionCard({
  title,
  subtitle,
  children,
}: {
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="panel-card space-y-4">
      {title || subtitle ? (
        <div>
          {title ? <h3 className="text-2xl">{title}</h3> : null}
          {subtitle ? <p className="mt-1 text-sm text-slate-600">{subtitle}</p> : null}
        </div>
      ) : null}
      {children}
    </section>
  );
}
