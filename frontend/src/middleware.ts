import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { jwtVerify } from "jose";

import { defaultRouteForRole, isRouteAllowedForRole } from "@/lib/routes";

const AUTH_COOKIE_NAME = process.env.AUTH_COOKIE_NAME ?? "ecoe_session";
const JWT_ISSUER = process.env.JWT_ISSUER ?? "ecoe-backend";
const JWT_AUDIENCE = process.env.JWT_AUDIENCE ?? "ecoe-web";
// SECRET_KEY llega por env server-side (compartida con el backend, HS256).
// Nunca se expone al navegador: el middleware corre en el servidor.
const SECRET_KEY = process.env.SECRET_KEY ?? "";

const PUBLIC_PATHS = ["/login"];

async function verifySession(token: string): Promise<{ role: string } | null> {
  if (!SECRET_KEY) {
    // Sin clave configurada (dev sin .env): degradar a "cookie presente".
    return { role: "" };
  }
  try {
    const { payload } = await jwtVerify(token, new TextEncoder().encode(SECRET_KEY), {
      issuer: JWT_ISSUER,
      audience: JWT_AUDIENCE,
      algorithms: ["HS256"],
    });
    return { role: typeof payload.role === "string" ? payload.role : "" };
  } catch {
    return null;
  }
}

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Allow public paths
  if (PUBLIC_PATHS.some((path) => pathname === path)) {
    return NextResponse.next();
  }

  // Allow static assets and API routes (proxied to backend)
  if (
    pathname.startsWith("/_next") ||
    pathname.startsWith("/api") ||
    pathname.match(/\.(ico|png|svg|jpg|jpeg|gif|css|js|woff2?)$/)
  ) {
    return NextResponse.next();
  }

  const authCookie = request.cookies.get(AUTH_COOKIE_NAME);
  if (!authCookie?.value) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("redirect", pathname);
    return NextResponse.redirect(loginUrl);
  }

  // Validate signature/expiry of the JWT, not just cookie presence.
  const session = await verifySession(authCookie.value);
  if (!session) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("redirect", pathname);
    const response = NextResponse.redirect(loginUrl);
    response.cookies.delete(AUTH_COOKIE_NAME);
    return response;
  }

  // Redirect "/" to the role's home
  if (pathname === "/") {
    return NextResponse.redirect(new URL(defaultRouteForRole(session.role), request.url));
  }

  // Role-based route gating (defense in depth: the backend authorizes too).
  if (session.role && !isRouteAllowedForRole(pathname, session.role)) {
    return NextResponse.redirect(new URL(defaultRouteForRole(session.role), request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
