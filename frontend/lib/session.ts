import type { NextResponse } from "next/server";

/**
 * Sesiunea trăiește în două cookie-uri httpOnly:
 * - `auth-token`     — JWT-ul Supabase, valabil ~1 oră, trimis la backend
 * - `refresh-token`  — se schimbă pe un JWT nou când primul expiră
 *
 * Fără al doilea, utilizatorul era deconectat tăcut după o oră și primea
 * „Token invalid sau expirat" la orice acțiune, fără să înțeleagă de ce.
 */
export const AUTH_COOKIE = "auth-token";
export const REFRESH_COOKIE = "refresh-token";

const REFRESH_MAX_AGE_S = 30 * 24 * 3600; // 30 de zile

export type SupabaseSession = {
  access_token: string;
  refresh_token?: string;
  expires_at?: number;
};

/** Scrie cookie-urile de sesiune pe un răspuns. */
export function setSessionCookies(
  response: NextResponse,
  session: SupabaseSession
): void {
  const maxAge = session.expires_at
    ? session.expires_at - Math.floor(Date.now() / 1000)
    : 3600;

  response.cookies.set(AUTH_COOKIE, session.access_token, {
    httpOnly: true,
    secure: true,
    sameSite: "lax",
    maxAge: Math.max(maxAge, 0),
    path: "/",
  });

  if (session.refresh_token) {
    response.cookies.set(REFRESH_COOKIE, session.refresh_token, {
      httpOnly: true,
      secure: true,
      sameSite: "lax",
      maxAge: REFRESH_MAX_AGE_S,
      path: "/",
    });
  }
}

/** Șterge ambele cookie-uri (logout). */
export function clearSessionCookies(response: NextResponse): void {
  for (const name of [AUTH_COOKIE, REFRESH_COOKIE]) {
    response.cookies.set(name, "", {
      httpOnly: true,
      secure: true,
      sameSite: "lax",
      maxAge: 0,
      path: "/",
    });
  }
}

/**
 * Schimbă refresh token-ul pe o sesiune nouă. Întoarce null dacă Supabase îl
 * refuză (revocat, expirat) — caz în care utilizatorul chiar trebuie să se
 * autentifice din nou.
 */
export async function refreshSession(
  refreshToken: string
): Promise<SupabaseSession | null> {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!supabaseUrl || !anonKey) return null;

  try {
    const res = await fetch(
      `${supabaseUrl}/auth/v1/token?grant_type=refresh_token`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          apikey: anonKey,
          Authorization: `Bearer ${anonKey}`,
        },
        body: JSON.stringify({ refresh_token: refreshToken }),
        cache: "no-store",
      }
    );
    if (!res.ok) return null;
    const json = (await res.json()) as SupabaseSession;
    return json.access_token ? json : null;
  } catch {
    return null;
  }
}
