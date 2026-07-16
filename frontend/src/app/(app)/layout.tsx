import { AppShell } from "@/components/app-shell";

export default function ProtectedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AppShell
      title="Operación académica del ECOE"
      description="Gestiona planificación, pilotaje, ejecución, contingencia y resultados desde un mismo panel."
    >
      {children}
    </AppShell>
  );
}
