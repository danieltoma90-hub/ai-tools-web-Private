import { loginAction } from "@/app/actions/auth";

const SESSION_KEY = "auth-token";

export async function getToken(): Promise<string | null> {
  if (typeof window === "undefined") return null;

  // Fast path: token already cached in this tab's sessionStorage
  const cached = sessionStorage.getItem(SESSION_KEY);
  if (cached) return cached;

  // Fallback: read from HttpOnly cookie via server route (handles new tabs / page refresh)
  try {
    const res = await fetch("/api/auth/get-token");
    if (res.ok) {
      const { token } = (await res.json()) as { token: string | null };
      if (token) {
        sessionStorage.setItem(SESSION_KEY, token);
        return token;
      }
    }
  } catch {
    // network error — return null, caller handles it
  }

  return null;
}

export async function login(email: string, password: string) {
  // loginAction runs on the server — no browser fetch to Supabase at all
  const { access_token } = await loginAction(email, password);
  sessionStorage.setItem(SESSION_KEY, access_token);
}

export async function logout() {
  if (typeof window !== "undefined") {
    sessionStorage.removeItem(SESSION_KEY);
  }
  await fetch("/api/auth/clear-session", { method: "POST" });
  window.location.href = "/login";
}
