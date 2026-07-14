import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  let email: string;
  let password: string;

  try {
    const formData = await request.formData();
    email = String(formData.get("email") ?? "");
    password = String(formData.get("password") ?? "");
  } catch {
    return NextResponse.redirect(
      new URL("/login?error=server_error", request.url)
    );
  }

  if (!email || !password) {
    return NextResponse.redirect(
      new URL("/login?error=invalid_credentials", request.url)
    );
  }

  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  if (!supabaseUrl || !anonKey) {
    return NextResponse.redirect(
      new URL("/login?error=server_error", request.url)
    );
  }

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
    const access_token: string = json.access_token;
    const expires_at: number = json.expires_at;

    const maxAge = expires_at
      ? expires_at - Math.floor(Date.now() / 1000)
      : 3600;

    const response = NextResponse.redirect(new URL("/dashboard", request.url), {
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
  } catch {
    return NextResponse.redirect(
      new URL("/login?error=server_error", request.url)
    );
  }
}
