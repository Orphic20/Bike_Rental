import { api, ApiError } from "@/lib/api";
import { isSupabaseConfigured, supabase } from "@/lib/supabase";
import type { User } from "@/lib/types";
import type { Session } from "@supabase/supabase-js";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

interface AuthContextValue {
  session: Session | null;
  /** The row from our own `users` table, not the Supabase auth user. */
  profile: User | null;
  loading: boolean;
  /** Set when a session exists but the backend rejected it. */
  error: string | null;
  configured: boolean;
  signInWithGoogle: () => Promise<void>;
  signInWithPassword: (email: string, password: string) => Promise<void>;
  signUpWithPassword: (
    email: string,
    password: string,
    name: string,
  ) => Promise<{ needsConfirmation: boolean }>;
  signOut: () => Promise<void>;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

function requireClient() {
  if (!supabase) {
    throw new Error(
      "Authentication is not configured. Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY.",
    );
  }
  return supabase;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [profile, setProfile] = useState<User | null>(null);
  const [loading, setLoading] = useState(isSupabaseConfigured);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!supabase) return;

    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      if (!data.session) setLoading(false);
    });

    const { data: listener } = supabase.auth.onAuthStateChange((_event, next) => {
      setSession(next);
      if (!next) {
        setProfile(null);
        setError(null);
        setLoading(false);
      }
    });

    return () => listener.subscription.unsubscribe();
  }, []);

  // The profile lives in our database, created by the on_auth_user_created
  // trigger, so it is fetched separately from the Supabase session.
  useEffect(() => {
    if (!session) return;

    const controller = new AbortController();
    let cancelled = false;

    setLoading(true);
    api
      .me(controller.signal)
      .then((user) => {
        if (cancelled) return;
        setProfile(user);
        setError(null);
      })
      .catch((cause) => {
        if (cancelled || controller.signal.aborted) return;
        setProfile(null);
        setError(
          cause instanceof ApiError
            ? cause.message
            : "Could not load your profile.",
        );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [session]);

  const refreshProfile = useCallback(async () => {
    if (!session) return;
    try {
      setProfile(await api.me());
      setError(null);
    } catch (cause) {
      setError(
        cause instanceof ApiError ? cause.message : "Could not load your profile.",
      );
    }
  }, [session]);

  const signInWithGoogle = useCallback(async () => {
    const client = requireClient();
    const { error: cause } = await client.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: window.location.origin },
    });
    if (cause) throw new Error(cause.message);
  }, []);

  const signInWithPassword = useCallback(async (email: string, password: string) => {
    const client = requireClient();
    const { error: cause } = await client.auth.signInWithPassword({
      email,
      password,
    });
    if (cause) throw new Error(cause.message);
  }, []);

  const signUpWithPassword = useCallback(
    async (email: string, password: string, name: string) => {
      const client = requireClient();
      const { data, error: cause } = await client.auth.signUp({
        email,
        password,
        // The database trigger copies this into users.name when the auth row
        // is created, so the profile is not left with an empty name.
        options: { data: { name, full_name: name } },
      });
      if (cause) throw new Error(cause.message);
      return { needsConfirmation: data.session === null };
    },
    [],
  );

  const signOut = useCallback(async () => {
    await requireClient().auth.signOut();
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      session,
      profile,
      loading,
      error,
      configured: isSupabaseConfigured,
      signInWithGoogle,
      signInWithPassword,
      signUpWithPassword,
      signOut,
      refreshProfile,
    }),
    [
      session,
      profile,
      loading,
      error,
      signInWithGoogle,
      signInWithPassword,
      signUpWithPassword,
      signOut,
      refreshProfile,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
