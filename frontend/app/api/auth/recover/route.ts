import { NextRequest, NextResponse } from "next/server";

// Linkul din email duce la /auth/callback — aceeași adresă ca la invitații, deci deja aprobată în
// Supabase (Authentication → URL Configuration). Callback-ul recunoaște resetarea (type=recovery).
const CALLBACK_URL = process.env.NEXT_PUBLIC_APP_URL
  ? `${process.env.NEXT_PUBLIC_APP_URL}/auth/callback`
  : "https://ai-tools-web-three.vercel.app/auth/callback";

/** „Am uitat parola”: Supabase trimite pe email linkul de resetare.
 *  Răspunsul e același indiferent dacă adresa are cont — pagina nu dezvăluie cine are cont. */
export async function POST(request: NextRequest) {
  const inapoi = (query: string) =>
    NextResponse.redirect(new URL(`/login/parola-uitata?${query}`, request.url), { status: 303 });

  let email = "";
  try {
    const form = await request.formData();
    email = String(form.get("email") ?? "").trim().toLowerCase();
  } catch {
    return inapoi("eroare=server");
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return inapoi("eroare=email");

  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!supabaseUrl || !anonKey) return inapoi("eroare=server");

  try {
    const res = await fetch(
      `${supabaseUrl}/auth/v1/recover?redirect_to=${encodeURIComponent(CALLBACK_URL)}`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          apikey: anonKey,
          Authorization: `Bearer ${anonKey}`,
        },
        body: JSON.stringify({ email }),
        cache: "no-store",
      }
    );
    // Supabase limitează cererile repetate (un link pe minut pentru aceeași adresă)
    if (res.status === 429) return inapoi("eroare=prea_des");
    return inapoi("trimis=1");
  } catch {
    return inapoi("eroare=server");
  }
}
