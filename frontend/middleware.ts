import { NextResponse, type NextRequest } from "next/server";
import { jwtVerify } from "jose";

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const jwtSecretRaw = process.env.SUPABASE_JWT_SECRET;
const JWT_SECRET = jwtSecretRaw
  ? new TextEncoder().encode(jwtSecretRaw)
  : null;

async function isAuthenticated(token: string | undefined): Promise<boolean> {
  if (!token || !JWT_SECRET) return false;
  try {
    await jwtVerify(token, JWT_SECRET, {
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
