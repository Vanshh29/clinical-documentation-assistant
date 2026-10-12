import { useQueryClient } from '@tanstack/react-query';
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { api, configureApi } from './api';
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
  loading: boolean;
  login: (email: string, password: string) => Promise<Me>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(readToken);
  const [user, setUser] = useState<Me | null>(null);
  const [loading, setLoading] = useState<boolean>(() => readToken() !== null);
  const queryClient = useQueryClient();

  const logout = useCallback(() => {
    try {
      sessionStorage.removeItem(STORAGE_KEY);
    } catch {
      /* storage unavailable */
    }
    setToken(null);
    setUser(null);
    queryClient.clear();
  }, [queryClient]);

  configureApi({ getToken: () => token, onUnauthorized: logout });

  useEffect(() => {
    if (!token || user) return;
    let active = true;
    api<Me>('/me')
      .then((me) => active && setUser(me))
      .catch(() => active && logout())
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [token, user, logout]);

  const login = useCallback(
    async (email: string, password: string) => {
      const res = await api<{ access_token: string }>('/auth/token', {
        method: 'POST',
        json: { email, password },
      });
      configureApi({
        getToken: () => res.access_token,
        onUnauthorized: logout,
      });
      const me = await api<Me>('/me');
      try {
        sessionStorage.setItem(STORAGE_KEY, res.access_token);
      } catch {
        /* storage unavailable: session lasts until reload */
      }
      setToken(res.access_token);
      setUser(me);
      return me;
    },
    [logout],
  );

  const value = useMemo(() => ({ user, loading, login, logout }), [user, loading, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
