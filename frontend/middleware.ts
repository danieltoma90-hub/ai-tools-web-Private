import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

export async function middleware(request: NextRequest) {
  const response = NextResponse.next();
  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    { cookies: { getAll: () => request.cookies.getAll(), setAll: () => {} } }
  );

  const {
    data: { session },
  } = await supabase.auth.getSession();
  const isPublic = request.nextUrl.pathname.startsWith("/login");

  if (!session && !isPublic) {
    return NextResponse.redirect(new URL("/login", request.url));
  }
  if (session && request.nextUrl.pathname === "/login") {
    return NextResponse.redirect(new URL("/minuta", request.url));
  }
  return response;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
