/* Coastal Utility Atelier: warm daylight, editorial asymmetry, restrained clay-red cues. */
import { useAuth } from "@/contexts/AuthContext";
import { ArrowRight, X } from "lucide-react";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";

type Mode = "signIn" | "signUp";

export function AuthDialog({ onClose }: { onClose: () => void }) {
  const { configured, signInWithGoogle, signInWithPassword, signUpWithPassword } =
    useAuth();
  const [mode, setMode] = useState<Mode>("signIn");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (mode === "signIn") {
        await signInWithPassword(email, password);
        toast.success("Signed in");
        onClose();
      } else {
        const { needsConfirmation } = await signUpWithPassword(
          email,
          password,
          name.trim(),
        );
        if (needsConfirmation) {
          toast.success("Check your email", {
            description: "Confirm your address, then sign in.",
          });
          setMode("signIn");
        } else {
          toast.success("Account created");
          onClose();
        }
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  };

  const google = async () => {
    setError(null);
    setBusy(true);
    try {
      // Redirects away from the page, so there is nothing to close on success.
      await signInWithGoogle();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Something went wrong.");
      setBusy(false);
    }
  };

  return (
    <div
      className="booking-date-modal-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        className="booking-date-modal auth-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="auth-title"
      >
        <button className="booking-date-close" onClick={onClose} aria-label="Close">
          <X size={17} />
        </button>

        <span className="landing-eyebrow">
          <span className="eyebrow-rule" />
          {mode === "signIn" ? "Welcome back" : "Join the shop"}
        </span>
        <h2 id="auth-title">
          {mode === "signIn" ? "Sign in to book." : "Create your account."}
        </h2>
        <p>
          Your full name must match the physical ID you present at Bagong Sikat.
        </p>

        {!configured ? (
          <p className="auth-error" role="alert">
            Authentication is not configured. Add <code>VITE_SUPABASE_URL</code> and{" "}
            <code>VITE_SUPABASE_ANON_KEY</code> to <code>Frontend/.env</code>, then
            restart the dev server.
          </p>
        ) : (
          <>
            <button
              type="button"
              className="google-button"
              onClick={google}
              disabled={busy}
            >
              <GoogleGlyph /> Continue with Google
            </button>

            <div className="auth-divider">
              <span>or use your email</span>
            </div>

            <form className="auth-form" onSubmit={submit}>
              {mode === "signUp" && (
                <label>
                  Full government name
                  <input
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                    autoComplete="name"
                    required
                    placeholder="Mia Santos"
                  />
                </label>
              )}
              <label>
                Email address
                <input
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  autoComplete="email"
                  required
                  placeholder="you@email.com"
                />
              </label>
              <label>
                Password
                <input
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  autoComplete={
                    mode === "signIn" ? "current-password" : "new-password"
                  }
                  required
                  minLength={8}
                  placeholder="At least 8 characters"
                />
              </label>

              {error && (
                <p className="auth-error" role="alert">
                  {error}
                </p>
              )}

              <button
                className="primary-button full-button"
                type="submit"
                disabled={busy}
              >
                {busy
                  ? "Working…"
                  : mode === "signIn"
                    ? "Sign in"
                    : "Create account"}
                <ArrowRight size={15} />
              </button>
            </form>

            <button
              type="button"
              className="ghost-action auth-switch"
              onClick={() => {
                setMode(mode === "signIn" ? "signUp" : "signIn");
                setError(null);
              }}
            >
              {mode === "signIn"
                ? "New here? Create an account"
                : "Already have an account? Sign in"}
            </button>
          </>
        )}
      </div>
    </div>
  );
}

function GoogleGlyph() {
  return (
    <svg viewBox="0 0 18 18" width="15" height="15" aria-hidden="true">
      <path
        fill="#4285F4"
        d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62Z"
      />
      <path
        fill="#34A853"
        d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.8.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H.96v2.33A9 9 0 0 0 9 18Z"
      />
      <path
        fill="#FBBC05"
        d="M3.97 10.72a5.4 5.4 0 0 1 0-3.44V4.95H.96a9 9 0 0 0 0 8.1l3.01-2.33Z"
      />
      <path
        fill="#EA4335"
        d="M9 3.58c1.32 0 2.5.46 3.44 1.35l2.58-2.58C13.46.89 11.43 0 9 0A9 9 0 0 0 .96 4.95l3.01 2.33C4.68 5.16 6.66 3.58 9 3.58Z"
      />
    </svg>
  );
}
