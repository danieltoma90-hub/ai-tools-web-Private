import { NextRequest, NextResponse } from "next/server";
import { setSessionCookies } from "@/lib/session";

const MIN_LUNGIME = 8; // aceeași regulă ca la schimbarea parolei din pagina Cont

/** Setează parola nouă cu sesiunea din linkul de resetare și lasă utilizatorul autentificat. */
export async function POST(request: NextRequest) {
  let body: { access_token?: unknown; refresh_token?: unknown; expires_in?: unknown; parola?: unknown };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "server_error" }, { status: 400 });
  }
  const { access_token, refresh_token, expires_in, parola } = body;
  if (typeof access_token !== "string" || !access_token) {
    return NextResponse.json({ error: "link_expirat" }, { status: 401 });
  }
  if (typeof parola !== "string" || parola.length < MIN_LUNGIME) {
    return NextResponse.json({ error: "weak_password" }, { status: 422 });
  }

  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!supabaseUrl || !anonKey) return NextResponse.json({ error: "server_error" }, { status: 500 });

  let res: Response;
  try {
    res = await fetch(`${supabaseUrl}/auth/v1/user`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        apikey: anonKey,
        Authorization: `Bearer ${access_token}`,
      },
      body: JSON.stringify({ password: parola }),
      cache: "no-store",
    });
  } catch {
    return NextResponse.json({ error: "server_error" }, { status: 502 });
  }

  if (!res.ok) {
    const json = await res.json().catch(() => ({}));
    const cod = String(json.error_code ?? json.code ?? "").toLowerCase();
    const text = String(json.msg ?? json.message ?? json.error_description ?? "").toLowerCase();
    if (res.status === 401 || res.status === 403 || cod.includes("jwt") || cod === "session_not_found") {
      return NextResponse.json({ error: "link_expirat" }, { status: 401 });
    }
    if (cod === "same_password" || text.includes("different") || text.includes("same")) {
      return NextResponse.json({ error: "same_password" }, { status: 422 });
    }
    if (cod === "weak_password" || text.includes("weak") || text.includes("characters")) {
      return NextResponse.json({ error: "weak_password" }, { status: 422 });
    }
    return NextResponse.json({ error: "server_error" }, { status: 502 });
  }

  const response = NextResponse.json({ ok: true });
  const durata = typeof expires_in === "number" && expires_in > 0 ? expires_in : 3600;
  setSessionCookies(response, {
    access_token,
    refresh_token: typeof refresh_token === "string" ? refresh_token : undefined,
    expires_at: Math.floor(Date.now() / 1000) + durata,
  });
  return response;
}
