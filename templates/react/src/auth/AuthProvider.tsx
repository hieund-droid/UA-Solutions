/**
 * hq-apero-sso React integration.
 *
 * This is the ONLY place auth state lives. Components consume via `useAuth()`.
 * Replace the stub with the real client from https://github.com/Apero-Vibecode/hq-apero-sso.
 */

import { createContext, useContext, useMemo, useState, type ReactNode } from 'react';

import { config } from '../lib/config';

export interface User {
  sub: string;
  email: string;
  groups: readonly string[];
}

interface AuthState {
  user: User | null;
  isLoading: boolean;
  login: () => void;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  // TODO[platform]: replace this stub with the real hq-apero-sso React client.
  //   import { useAperoSSO } from 'hq-apero-sso/react';
  //   const sso = useAperoSSO({ issuer: config.sso.issuer, clientId: config.sso.clientId });
  //   return <AuthContext.Provider value={sso}>{children}</AuthContext.Provider>;
  void config;
  const [user] = useState<User | null>(null);
  const value = useMemo<AuthState>(
    () => ({
      user,
      isLoading: false,
      login: () => {
        throw new Error('SSO not yet wired — see src/auth/AuthProvider.tsx');
      },
      logout: () => {
        throw new Error('SSO not yet wired — see src/auth/AuthProvider.tsx');
      },
    }),
    [user],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
