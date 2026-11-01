import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import AuthPage from "./pages/AuthPage";
import Studio from "./pages/Studio";

function RequireAuth({ children }) {
  const { user, ready } = useAuth();
  if (!ready) {
    return (
      <div className="boot">
        <p>Opening AskDB…</p>
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function GuestOnly({ children }) {
  const { user, ready } = useAuth();
  if (!ready) {
    return (
      <div className="boot">
        <p>Opening AskDB…</p>
      </div>
    );
  }
  if (user) return <Navigate to="/" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route
        path="/login"
        element={
          <GuestOnly>
            <AuthPage mode="login" />
          </GuestOnly>
        }
      />
      <Route
        path="/register"
        element={
          <GuestOnly>
            <AuthPage mode="register" />
          </GuestOnly>
        }
      />
      <Route
        path="/"
        element={
          <RequireAuth>
            <Studio />
          </RequireAuth>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
