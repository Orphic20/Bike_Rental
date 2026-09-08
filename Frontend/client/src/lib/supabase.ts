import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const url = import.meta.env.VITE_SUPABASE_URL;
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

/**
 * Null when the environment variables are absent.
 *
 * The landing page and catalogue are public, so an unconfigured deployment
 * should still render rather than crashing on import. Everything that needs a
 * session checks this first and tells the user what is missing.
 */
export const supabase: SupabaseClient | null =
  url && anonKey
    ? createClient(url, anonKey, {
        auth: {
          persistSession: true,
          autoRefreshToken: true,
          detectSessionInUrl: true,
        },
      })
    : null;

export const isSupabaseConfigured = supabase !== null;

/** Bearer token for the FastAPI service, or null when signed out. */
export async function getAccessToken(): Promise<string | null> {
  if (!supabase) return null;
  // getSession refreshes an expired token before returning it, so this is
  // safer than holding onto the token from onAuthStateChange.
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}
