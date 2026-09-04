import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from 'react';
import type { Session, User } from '@supabase/supabase-js';
import { supabase } from '../lib/supabase';

// ── Types ─────────────────────────────────────────────────────────────────────
interface AuthContextValue {
  user:        User    | null;
  session:     Session | null;
  /** True while the initial session is being resolved from storage. */
  initialising: boolean;
  signIn:  (email: string, password: string) => Promise<void>;
  signUp:  (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
}

// ── Context ───────────────────────────────────────────────────────────────────
const AuthCtx = createContext<AuthContextValue>({
  user:         null,
  session:      null,
  initialising: true,
  signIn:  async () => {},
  signUp:  async () => {},
  signOut: async () => {},
});

// ── Provider ──────────────────────────────────────────────────────────────────
export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user,         setUser]         = useState<User    | null>(null);
  const [session,      setSession]      = useState<Session | null>(null);
  const [initialising, setInitialising] = useState(true);

  useEffect(() => {
    // 1. Get current session on mount (handles page refreshes)
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setUser(data.session?.user ?? null);
      setInitialising(false);
    });

    // 2. Subscribe to auth state changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, s) => {
      setSession(s);
      setUser(s?.user ?? null);
    });

    return () => subscription.unsubscribe();
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) throw new Error(error.message);
  }, []);

  const signUp = useCallback(async (email: string, password: string) => {
    const { error } = await supabase.auth.signUp({ email, password });
    if (error) throw new Error(error.message);
  }, []);

  const signOut = useCallback(async () => {
    const { error } = await supabase.auth.signOut();
    if (error) throw new Error(error.message);
  }, []);

  return (
    <AuthCtx.Provider value={{ user, session, initialising, signIn, signUp, signOut }}>
      {children}
    </AuthCtx.Provider>
  );
};

// ── Hook ──────────────────────────────────────────────────────────────────────
export const useAuth = () => useContext(AuthCtx);
