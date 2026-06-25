import { createClient } from "@supabase/supabase-js";

export const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);

// Sync auth state to cookie so middleware can read it (browser-only)
if (typeof window !== "undefined") {
  supabase.auth.onAuthStateChange((_event, session) => {
    document.cookie = `auth-session=1; path=/; max-age=${session ? 86400 : 0}; SameSite=Lax`;
  });
}
