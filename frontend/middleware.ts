import { NextResponse, type NextRequest } from "next/server";
import { createRemoteJWKSet, jwtVerify } from "jose";

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";

// Supabase issues ES256 tokens (asymmetric) — verify via public JWKS endpoint.
// createRemoteJWKSet caches keys in memory and re-fetches on key rotation.
const JWKS = SUPABASE_URL
  ? createRemoteJWKSet(
      new URL(`${SUPABASE_URL}/auth/v1/.well-known/jwks.json`)
    )
  : null;

async function isAuthenticated(token: string | undefined): Promise<boolean> {
  if (!token || !JWKS) return false;
  try {
    await jwtVerify(token, JWKS, {
      issuer: `${SUPABASE_URL}/auth/v1`,
    });
    return true;
  } catch {
    return false;
  }
}

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const isPublic =
    pathname.startsWith("/login") ||
    pathname.startsWith("/auth/") ||
    pathname.startsWith("/api/auth/");
  const token = request.cookies.get("auth-token")?.value;
  const authenticated = await isAuthenticated(token);

  if (!authenticated && !isPublic) {
    return NextResponse.redirect(new URL("/login", request.url));
  }
  if (authenticated && pathname === "/login") {
    return NextResponse.redirect(new URL("/minuta", request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
