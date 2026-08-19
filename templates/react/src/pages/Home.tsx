import { useAuth } from '../auth/AuthProvider';

export function Home() {
  const { user, login, logout } = useAuth();
  return (
    <main>
      <h1>Apero App</h1>
      {user ? (
        <>
          <p>Signed in as {user.email}</p>
          <button onClick={logout}>Sign out</button>
        </>
      ) : (
        <button onClick={login}>Sign in with Apero SSO</button>
      )}
    </main>
  );
}
