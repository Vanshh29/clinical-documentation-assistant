import { useQueryClient } from '@tanstack/react-query';
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { ApiError, api, configureApi } from './api';
import type { Me } from './types';

const STORAGE_KEY = 'cda.token';

function readToken(): string | null {
  try {
    return sessionStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

interface AuthState {
  user: Me | null;
  /** True while a stored session is being restored. */
  loading: boolean;
  /** Set when the session could not be restored for a reason other than it being invalid. */
  error: string | null;
  retry: () => void;
  login: (email: string, password: string) => Promise<Me>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(readToken);
  const [user, setUser] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const queryClient = useQueryClient();

  const logout = useCallback(() => {
    try {
      sessionStorage.removeItem(STORAGE_KEY);
    } catch {
      /* storage unavailable */
    }
    setToken(null);
    setUser(null);
    setError(null);
    queryClient.clear();
  }, [queryClient]);

  configureApi({ getToken: () => token, onUnauthorized: logout });

  // Restore the session after a page load. Only a 401 ends it: a network blip, a restarting server or a
  // request cancelled by a quick navigation must never sign the person out.
  useEffect(() => {
    if (!token || user) return;
    let active = true;
    api<Me>('/me')
      .then((me) => {
        if (active) {
          setError(null);
          setUser(me);
        }
      })
      .catch((e: unknown) => {
        if (!active) return;
        if (e instanceof ApiError && e.status === 401) logout();
        else setError(e instanceof Error ? e.message : 'Could not restore your session.');
      });
    return () => {
      active = false;
    };
  }, [token, user, attempt, logout]);

  const login = useCallback(
    async (email: string, password: string) => {
      const res = await api<{ access_token: string }>('/auth/token', { method: 'POST', json: { email, password } });
      configureApi({ getToken: () => res.access_token, onUnauthorized: logout });
      const me = await api<Me>('/me');
      try {
        sessionStorage.setItem(STORAGE_KEY, res.access_token);
      } catch {
        /* storage unavailable: the session lasts until reload */
      }
      setToken(res.access_token);
      setUser(me);
      setError(null);
      return me;
    },
    [logout],
  );

  const retry = useCallback(() => {
    setError(null);
    setAttempt((n) => n + 1);
  }, []);

  const loading = token !== null && user === null && error === null;
  const value = useMemo(
    () => ({ user, loading, error, retry, login, logout }),
    [user, loading, error, retry, login, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
