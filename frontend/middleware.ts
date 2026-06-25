import { NextResponse, type NextRequest } from "next/server";

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";

function isValidSupabaseJwt(token: string | undefined): boolean {
  if (!token) return false;
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return false;
    const padded = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const payload = JSON.parse(atob(padded)) as Record<string, unknown>;
    const now = Math.floor(Date.now() / 1000);
    return (
      payload.iss === `${SUPABASE_URL}/auth/v1` &&
      typeof payload.exp === "number" &&
      payload.exp > now
    );
  } catch {
    return false;
  }
}

export function middleware(request: NextRequest) {
  const isPublic = request.nextUrl.pathname.startsWith("/login");
  const token = request.cookies.get("auth-token")?.value;
  const authenticated = isValidSupabaseJwt(token);

  if (!authenticated && !isPublic) {
    return NextResponse.redirect(new URL("/login", request.url));
  }
  if (authenticated && request.nextUrl.pathname === "/login") {
    return NextResponse.redirect(new URL("/minuta", request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
