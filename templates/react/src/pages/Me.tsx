import { useAuth } from '../auth/AuthProvider';

export function Me() {
  const { user } = useAuth();
  if (!user) return null;
  return (
    <main>
      <h1>Your profile</h1>
      <dl>
        <dt>Subject</dt>
        <dd>{user.sub}</dd>
        <dt>Email</dt>
        <dd>{user.email}</dd>
        <dt>Groups</dt>
        <dd>{user.groups.join(', ') || '—'}</dd>
      </dl>
    </main>
  );
}
