import { NextResponse, type NextRequest } from "next/server";

// Decode JWT payload without signature verification.
// Real auth enforcement is on FastAPI (verifies signature on every API call).
// Middleware only checks presence and expiry for routing decisions.
function decodeJWTPayload(token: string): Record<string, unknown> | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    const b64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const padded = b64 + "=".repeat((4 - (b64.length % 4)) % 4);
    return JSON.parse(atob(padded));
  } catch {
    return null;
  }
}

function hasValidSession(token: string | undefined): boolean {
  if (!token) return false;
  const payload = decodeJWTPayload(token);
  if (!payload) return false;
  const exp = payload.exp;
  if (typeof exp !== "number") return false;
  return exp > Math.floor(Date.now() / 1000);
}

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const isPublic =
    pathname.startsWith("/login") ||
    pathname.startsWith("/auth/") ||
    pathname.startsWith("/api/auth/");

  const token = request.cookies.get("auth-token")?.value;
  // Un access token expirat NU mai înseamnă deconectare: cât timp există refresh
  // token, proxy-ul obține unul nou la primul apel. Fără asta, utilizatorul era
  // aruncat la login după o oră deși sesiunea putea continua.
  const canRefresh = Boolean(request.cookies.get("refresh-token")?.value);
  const authenticated = hasValidSession(token) || canRefresh;

  if (!authenticated && !isPublic) {
    return NextResponse.redirect(new URL("/login", request.url));
  }
  if (authenticated && pathname === "/login") {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
