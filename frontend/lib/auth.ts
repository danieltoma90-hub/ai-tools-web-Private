import { supabase } from "./supabase";

export async function getToken(): Promise<string | null> {
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

export async function logout() {
  await supabase.auth.signOut();
  window.location.href = "/login";
}

export async function login(email: string, password: string) {
  const { error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) throw new Error(error.message);
}
