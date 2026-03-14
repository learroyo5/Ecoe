import { AppShell } from "@/components/app-shell";

export default function ProtectedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AppShell
      title="Operacion academica del ECOE"
      description="Gestiona planificacion, pilotaje, ejecucion, contingencia y resultados desde un mismo panel."
    >
      {children}
    </AppShell>
  );
}
