# Frontend — Plataforma ECOE

Next.js (App Router) + TypeScript + Tailwind CSS. Documentación general en el `README.md` de la raíz.

```bash
npm run dev      # desarrollo (necesita el backend en INTERNAL_API_URL)
npm test         # vitest
npm run lint
npm run build
```

- La API se consume por el mismo origen: `next.config.ts` reescribe `/api/:path*` hacia `INTERNAL_API_URL`.
- Rutas, roles y grupos de la barra lateral: `src/lib/routes.ts` (`NAV_ITEMS`).
- Flujo de punta a punta (Playwright): `../scripts/run_e2e.sh`, sobre un stack desechable. Nunca apuntarlo a producción.
