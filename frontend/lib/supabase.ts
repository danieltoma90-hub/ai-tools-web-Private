import { createClient } from "@supabase/supabase-js";

export const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);

// Sync JWT to cookie so middleware can verify it (browser-only, non-HttpOnly)
if (typeof window !== "undefined") {
  supabase.auth.onAuthStateChange((_event, session) => {
    if (session?.access_token) {
      const maxAge = (session.expires_at ?? 0) - Math.floor(Date.now() / 1000);
      document.cookie = `auth-token=${session.access_token}; path=/; max-age=${Math.max(maxAge, 0)}; SameSite=Lax`;
    } else {
      document.cookie = "auth-token=; path=/; max-age=0";
    }
  });
}
