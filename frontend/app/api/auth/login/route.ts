import { NextRequest, NextResponse } from "next/server";
import { setSessionCookies } from "@/lib/session";

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
    const response = NextResponse.redirect(new URL("/dashboard", request.url), {
      status: 303,
    });
    setSessionCookies(response, {
      access_token: json.access_token,
      refresh_token: json.refresh_token,
      expires_at: json.expires_at,
    });
    return response;
  } catch {
    return NextResponse.redirect(
      new URL("/login?error=server_error", request.url)
    );
  }
}
