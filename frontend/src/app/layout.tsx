import type { Metadata } from "next";
import { Bitter, Source_Sans_3 } from "next/font/google";

import "./globals.css";
import { AuthProvider } from "@/lib/auth";

const display = Bitter({
  subsets: ["latin"],
  variable: "--font-display",
});

const body = Source_Sans_3({
  subsets: ["latin"],
  variable: "--font-body",
});

export const metadata: Metadata = {
  title: "Proyecto ECOE Digital",
  description: "Plataforma de planificacion y ejecucion de ECOE/OSCE",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es" className={`${display.variable} ${body.variable}`} data-system="ecoe">
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
