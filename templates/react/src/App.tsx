import { Route, Routes } from 'react-router-dom';

import { RequireAuth } from './auth/RequireAuth';
import { Home } from './pages/Home';
import { Me } from './pages/Me';

export function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route
        path="/me"
        element={
          <RequireAuth>
            <Me />
          </RequireAuth>
        }
      />
    </Routes>
  );
}
