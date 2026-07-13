"use server";
import { cookies } from "next/headers";

/** Schimbă parola utilizatorului curent, după verificarea parolei actuale. */
export async function changePasswordAction(
  currentPassword: string,
  newPassword: string
): Promise<void> {
  const cookieStore = await cookies();
  const token = cookieStore.get("auth-token")?.value;
  if (!token) throw new Error("unauthorized");

  if (newPassword.length < 8) {
    throw new Error("weak_password");
  }

  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

  // 1) Aflam email-ul utilizatorului din tokenul de sesiune
  const userRes = await fetch(`${supabaseUrl}/auth/v1/user`, {
    headers: { apikey: anonKey, Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!userRes.ok) throw new Error("unauthorized");
  const { email } = await userRes.json();

  // 2) Verificam parola actuala printr-un sign-in
  const verifyRes = await fetch(
    `${supabaseUrl}/auth/v1/token?grant_type=password`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        apikey: anonKey,
        Authorization: `Bearer ${anonKey}`,
      },
      body: JSON.stringify({ email, password: currentPassword }),
      cache: "no-store",
    }
  );
  if (!verifyRes.ok) throw new Error("wrong_password");
  const session = await verifyRes.json();

  // 3) Setam parola noua pe sesiunea proaspat verificata
  const updateRes = await fetch(`${supabaseUrl}/auth/v1/user`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      apikey: anonKey,
      Authorization: `Bearer ${session.access_token}`,
    },
    body: JSON.stringify({ password: newPassword }),
    cache: "no-store",
  });
  if (!updateRes.ok) {
    const json = await updateRes.json().catch(() => ({}));
    const msg = (json.message || json.msg || "").toLowerCase();
    // Supabase refuza parola identica cu cea veche
    if (msg.includes("different") || msg.includes("same")) {
      throw new Error("same_password");
    }
    throw new Error("server_error");
  }
}
