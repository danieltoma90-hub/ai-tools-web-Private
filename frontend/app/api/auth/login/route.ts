import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  const formData = await request.formData();
  const email = String(formData.get("email") ?? "");
  const password = String(formData.get("password") ?? "");

  if (!email || !password) {
    return NextResponse.redirect(
      new URL("/login?error=invalid_credentials", request.url)
    );
  }

  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

  let access_token: string;
  let expires_at: number;

  try {
    const res = await fetch(
      `${supabaseUrl}/auth/v1/token?grant_type=password`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          apikey: anonKey,
          Authorization: `Bearer ${anonKey}`,
        },
        body: JSON.stringify({ email, password }),
        cache: "no-store",
      }
    );

    if (!res.ok) {
      return NextResponse.redirect(
        new URL("/login?error=invalid_credentials", request.url)
      );
    }

    const json = await res.json();
    access_token = json.access_token;
    expires_at = json.expires_at;
  } catch {
    return NextResponse.redirect(
      new URL("/login?error=server_error", request.url)
    );
  }

  const maxAge = expires_at
    ? expires_at - Math.floor(Date.now() / 1000)
    : 3600;

  const response = NextResponse.redirect(new URL("/minuta", request.url), {
    status: 303,
  });
  response.cookies.set("auth-token", access_token, {
    httpOnly: true,
    secure: true,
    sameSite: "lax",
    maxAge: Math.max(maxAge, 0),
    path: "/",
  });
  return response;
}
