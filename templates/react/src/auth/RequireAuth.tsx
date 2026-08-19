import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';

import { useAuth } from './AuthProvider';

export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) return <p>Loading…</p>;
  if (!user) return <Navigate to="/" state={{ from: location }} replace />;
  return <>{children}</>;
}
