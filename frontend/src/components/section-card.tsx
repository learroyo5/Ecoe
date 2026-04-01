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
          {title ? <h3 className="text-2xl md:text-3xl">{title}</h3> : null}
          {subtitle ? <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">{subtitle}</p> : null}
        </div>
      ) : null}
      {children}
    </section>
  );
}
