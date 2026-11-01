import { useState } from "react";
import { api } from "../api";

const EMPTY = {
  name: "",
  host: "localhost",
  port: "5432",
  database: "",
  username: "",
  password: "",
};

export default function ConnectModal({ onClose, onCreated }) {
  const [tab, setTab] = useState("postgres");
  const [form, setForm] = useState(EMPTY);
  const [file, setFile] = useState(null);
  const [sqliteName, setSqliteName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  function update(event) {
    setForm((current) => ({ ...current, [event.target.name]: event.target.value }));
  }

  async function savePostgres(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const created = await api("/api/connections", {
        method: "POST",
        body: JSON.stringify({
          name: form.name.trim(),
          host: form.host.trim(),
          port: Number(form.port),
          database: form.database.trim(),
          username: form.username.trim(),
          password: form.password,
        }),
      });
      onCreated(created);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function saveSqlite(event) {
    event.preventDefault();
    if (!file) {
      setError("Choose a SQLite file first.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const body = new FormData();
      body.append("file", file);
      if (sqliteName.trim()) body.append("name", sqliteName.trim());
      const created = await api("/api/connections/sqlite", { method: "POST", body });
      onCreated(created);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="connect-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-head">
          <h2 id="connect-title">Add a database</h2>
          <button type="button" className="text-button" onClick={onClose}>
            Close
          </button>
        </div>
        <div className="tabs">
          <button type="button" className={tab === "postgres" ? "tab active" : "tab"} onClick={() => setTab("postgres")}>
            PostgreSQL
          </button>
          <button type="button" className={tab === "sqlite" ? "tab active" : "tab"} onClick={() => setTab("sqlite")}>
            SQLite file
          </button>
        </div>
        {error ? <p className="banner banner-danger">{error}</p> : null}
        {tab === "postgres" ? (
          <form className="stack" onSubmit={savePostgres}>
            <p className="hint">
              From inside Docker, a database on your machine is usually <code>host.docker.internal</code>. The
              password is encrypted before it is stored.
            </p>
            <label className="field">
              Name
              <input name="name" value={form.name} onChange={update} required maxLength={120} />
            </label>
            <div className="split">
              <label className="field">
                Host
                <input name="host" value={form.host} onChange={update} required />
              </label>
              <label className="field">
                Port
                <input name="port" value={form.port} onChange={update} required inputMode="numeric" />
              </label>
            </div>
            <label className="field">
              Database
              <input name="database" value={form.database} onChange={update} required />
            </label>
            <label className="field">
              Username
              <input name="username" value={form.username} onChange={update} required autoComplete="off" />
            </label>
            <label className="field">
              Password
              <input
                name="password"
                type="password"
                value={form.password}
                onChange={update}
                required
                autoComplete="new-password"
              />
            </label>
            <button className="button" type="submit" disabled={busy}>
              {busy ? "Checking connection…" : "Save connection"}
            </button>
          </form>
        ) : (
          <form className="stack" onSubmit={saveSqlite}>
            <p className="hint">Upload a .db or .sqlite file up to 20 MB. AskDB only runs SELECT queries against it.</p>
            <label className="field">
              Display name
              <input value={sqliteName} onChange={(event) => setSqliteName(event.target.value)} maxLength={120} />
            </label>
            <label className="field">
              File
              <input
                type="file"
                accept=".db,.sqlite,.sqlite3,application/octet-stream"
                onChange={(event) => setFile(event.target.files?.[0] || null)}
                required
              />
            </label>
            <button className="button" type="submit" disabled={busy}>
              {busy ? "Uploading…" : "Upload SQLite"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
