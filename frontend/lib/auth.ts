import { supabase } from "./supabase";

export async function getToken(): Promise<string | null> {
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

export async function login(email: string, password: string) {
  const { data, error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) throw new Error(error.message);
  if (data.session) {
    await fetch("/api/auth/set-session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        access_token: data.session.access_token,
        expires_at: data.session.expires_at,
      }),
    });
  }
}

export async function logout() {
  await fetch("/api/auth/clear-session", { method: "POST" });
  await supabase.auth.signOut();
  window.location.href = "/login";
}
