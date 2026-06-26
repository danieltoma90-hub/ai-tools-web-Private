"use server";
import { cookies } from "next/headers";

export async function loginAction(email: string, password: string): Promise<void> {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
  const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

  const res = await fetch(`${supabaseUrl}/auth/v1/token?grant_type=password`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      apikey: supabaseAnonKey,
      Authorization: `Bearer ${supabaseAnonKey}`,
    },
    body: JSON.stringify({ email, password }),
    cache: "no-store",
  });

  const json = await res.json();
  if (!res.ok) {
    throw new Error(json.error_description || json.message || "Autentificare eșuată");
  }

  const { access_token, expires_at } = json as {
    access_token: string;
    expires_at: number;
  };

  const cookieStore = await cookies();
  const maxAge = expires_at ? expires_at - Math.floor(Date.now() / 1000) : 3600;
  cookieStore.set("auth-token", access_token, {
    httpOnly: true,
    secure: true,
    sameSite: "lax",
    maxAge: Math.max(maxAge, 0),
    path: "/",
  });
}
