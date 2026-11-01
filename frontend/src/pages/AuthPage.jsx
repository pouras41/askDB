import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth";

export default function AuthPage({ mode }) {
  const isLogin = mode === "login";
  const { login, register } = useAuth();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(event) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (isLogin) {
        await login(email.trim(), password);
      } else {
        await register(name.trim(), email.trim(), password);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-shell">
      <section className="auth-story">
        <p className="brand">AskDB</p>
        <p className="story-kicker">Natural language to SQL</p>
        <h1>Ask the database. Skip the blank query editor.</h1>
        <p className="story-copy">
          Write a question in plain language. AskDB uses Gemini to draft a read-only query, checks it,
          runs it, and draws a chart from the rows.
        </p>
        <div className="story-card">
          <p className="story-q">What are the top 5 products by paid revenue?</p>
          <pre>
            {`SELECT p.name, SUM(oi.quantity * oi.unit_price) AS revenue
FROM order_items oi
JOIN products p ON p.id = oi.product_id
JOIN orders o ON o.id = oi.order_id
WHERE o.status = 'paid'
GROUP BY p.name
ORDER BY revenue DESC
LIMIT 5`}
          </pre>
        </div>
      </section>
      <section className="auth-panel">
        <form className="auth-form" onSubmit={onSubmit}>
          <p className="brand brand-small">AskDB</p>
          <h2>{isLogin ? "Welcome back" : "Create your account"}</h2>
          <p className="muted">
            {isLogin
              ? "Sign in to question the Harbor & Co. demo, or a database you connect."
              : "Passwords are hashed. You get a signed session, then the studio."}
          </p>
          {error ? (
            <p className="banner banner-danger" role="alert">
              {error}
            </p>
          ) : null}
          {isLogin ? null : (
            <label className="field">
              Name
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                autoComplete="name"
                required
                maxLength={80}
              />
            </label>
          )}
          <label className="field">
            Email
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="email"
              required
            />
          </label>
          <label className="field">
            Password
            <span className="password-row">
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete={isLogin ? "current-password" : "new-password"}
                required
                minLength={isLogin ? 1 : 8}
              />
              <button type="button" className="text-button" onClick={() => setShowPassword((value) => !value)}>
                {showPassword ? "Hide" : "Show"}
              </button>
            </span>
          </label>
          {isLogin ? null : (
            <p className="hint">Use at least 8 characters, with a letter and a number.</p>
          )}
          <button className="button" type="submit" disabled={busy}>
            {busy ? "Please wait…" : isLogin ? "Sign in" : "Create account"}
          </button>
          <p className="switch">
            {isLogin ? "New here?" : "Already have an account?"}{" "}
            <Link to={isLogin ? "/register" : "/login"}>{isLogin ? "Create an account" : "Sign in"}</Link>
          </p>
        </form>
      </section>
    </main>
  );
}
