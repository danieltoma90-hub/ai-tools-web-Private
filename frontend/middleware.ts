import { NextResponse, type NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  const isPublic = request.nextUrl.pathname.startsWith("/login");
  const session = request.cookies.get("auth-session");

  if (!session && !isPublic) {
    return NextResponse.redirect(new URL("/login", request.url));
  }
  if (session && request.nextUrl.pathname === "/login") {
    return NextResponse.redirect(new URL("/minuta", request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
