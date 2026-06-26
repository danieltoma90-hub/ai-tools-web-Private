import { supabase } from "./supabase";

export async function getToken(): Promise<string | null> {
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

export async function login(email: string, password: string) {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
  const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

  // Use raw fetch with explicit ASCII-only headers to avoid supabase-js X-Client-Info injection
  const res = await fetch(`${supabaseUrl}/auth/v1/token?grant_type=password`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "apikey": supabaseAnonKey,
      "Authorization": `Bearer ${supabaseAnonKey}`,
    },
    body: JSON.stringify({ email, password }),
  });

  const json = await res.json();
  if (!res.ok) {
    throw new Error(json.error_description || json.message || "Autentificare eșuată");
  }

  const { access_token, refresh_token, expires_at } = json as {
    access_token: string;
    refresh_token: string;
    expires_at: number;
  };

  await supabase.auth.setSession({ access_token, refresh_token });

  await fetch("/api/auth/set-session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ access_token, expires_at }),
  });
}

export async function logout() {
  await fetch("/api/auth/clear-session", { method: "POST" });
  await supabase.auth.signOut();
  window.location.href = "/login";
}
