import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useAuth } from "../auth";
import ChartView from "../components/ChartView";
import ConnectModal from "../components/ConnectModal";
import { download, formatWhen, toCsv } from "../format";

const KEYWORDS = new Set(
  "select from where group by order limit offset join left right inner full outer on and or not as with distinct having union all case when then else end asc desc in is null like between".split(
    " ",
  ),
);

function SqlBlock({ sql }) {
  const parts = sql.split(/(\s+|[(),.*])/);
  return (
    <pre className="sql-block">
      {parts.map((part, index) =>
        KEYWORDS.has(part.toLowerCase()) ? (
          <span className="kw" key={`${part}-${index}`}>
            {part}
          </span>
        ) : (
          <span key={`${part}-${index}`}>{part}</span>
        ),
      )}
    </pre>
  );
}

function sortRows(rows, sort) {
  if (!sort.key) return rows;
  const copy = [...rows];
  copy.sort((leftRow, rightRow) => {
    const left = leftRow[sort.key];
    const right = rightRow[sort.key];
    if (left == null && right == null) return 0;
    if (left == null) return 1;
    if (right == null) return -1;
    const leftNumber = typeof left === "number" ? left : Number(left);
    const rightNumber = typeof right === "number" ? right : Number(right);
    const leftNumeric = typeof left === "number" || (typeof left === "string" && left.trim() !== "" && Number.isFinite(leftNumber));
    const rightNumeric = typeof right === "number" || (typeof right === "string" && right.trim() !== "" && Number.isFinite(rightNumber));
    let compared = 0;
    if (leftNumeric && rightNumeric) compared = leftNumber - rightNumber;
    else compared = String(left).localeCompare(String(right));
    return sort.dir === "asc" ? compared : -compared;
  });
  return copy;
}

export default function Studio() {
  const { user, logout } = useAuth();
  const [health, setHealth] = useState(null);
  const [connections, setConnections] = useState([]);
  const [activeId, setActiveId] = useState("demo");
  const [schema, setSchema] = useState(null);
  const [schemaError, setSchemaError] = useState("");
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [sqlDraft, setSqlDraft] = useState("");
  const [tab, setTab] = useState("table");
  const [sort, setSort] = useState({ key: null, dir: "asc" });
  const [history, setHistory] = useState([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [connectOpen, setConnectOpen] = useState(false);
  const [summary, setSummary] = useState(null);
  const [summarizing, setSummarizing] = useState(false);
  const [summaryError, setSummaryError] = useState("");
  const [autoSummarize, setAutoSummarize] = useState(() => {
    return localStorage.getItem("askdb_auto_summarize") === "true";
  });

  function toggleAutoSummarize(val) {
    setAutoSummarize(val);
    localStorage.setItem("askdb_auto_summarize", val ? "true" : "false");
  }

  const active = connections.find((item) => item.id === activeId) || null;

  useEffect(() => {
    let cancelled = false;
    api("/api/health")
      .then((data) => {
        if (!cancelled) setHealth(data);
      })
      .catch(() => {});
    api("/api/connections")
      .then((data) => {
        if (cancelled) return;
        setConnections(data);
        setActiveId((current) => data.some((item) => item.id === current) ? current : data[0]?.id || "demo");
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!activeId) return undefined;
    let cancelled = false;
    setSchema(null);
    setSchemaError("");
    api(`/api/connections/${activeId}/schema`)
      .then((data) => {
        if (!cancelled) setSchema(data);
      })
      .catch((err) => {
        if (!cancelled) setSchemaError(err.message);
      });
    api(`/api/history?connection_id=${encodeURIComponent(activeId)}`)
      .then((rows) => {
        if (!cancelled) setHistory(rows);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [activeId]);

  const visibleRows = useMemo(() => sortRows(result?.rows || [], sort), [result, sort]);

  function toggleSort(column) {
    setSort((current) => {
      if (current.key !== column) return { key: column, dir: "asc" };
      return { key: column, dir: current.dir === "asc" ? "desc" : "asc" };
    });
  }

  async function refreshConnections(nextId) {
    const data = await api("/api/connections");
    setConnections(data);
    if (nextId) setActiveId(nextId);
  }

  async function requestSummary(targetResult) {
    const current = targetResult || result;
    if (!current || !current.history_id) return;
    setSummarizing(true);
    setSummaryError("");
    try {
      const data = await api(`/api/query/${current.history_id}/summarize`, {
        method: "POST",
        body: JSON.stringify({
          columns: current.columns || [],
          rows: current.rows || [],
          stats: current.stats || [],
        }),
      });
      setSummary(data);
      const rows = await api(`/api/history?connection_id=${encodeURIComponent(activeId)}`);
      setHistory(rows);
    } catch (err) {
      setSummaryError(err.message || "Failed to generate insights.");
    } finally {
      setSummarizing(false);
    }
  }

  function selectFollowUp(followUpQuestion) {
    setQuestion(followUpQuestion);
    const input = document.getElementById("question");
    if (input) {
      input.focus();
      input.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }

  async function onAsk(event) {
    event.preventDefault();
    if (!question.trim()) return;
    setAsking(true);
    setError("");
    setSummary(null);
    setSummaryError("");
    try {
      const data = await api("/api/query", {
        method: "POST",
        body: JSON.stringify({ connection_id: activeId, question: question.trim() }),
      });
      setResult(data);
      setSqlDraft(data.sql);
      setSort({ key: null, dir: "asc" });
      setTab(data.chart === "table" ? "table" : "chart");
      const rows = await api(`/api/history?connection_id=${encodeURIComponent(activeId)}`);
      setHistory(rows);
      if (autoSummarize && data.rows && data.rows.length) {
        requestSummary(data);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setAsking(false);
    }
  }

  async function onRunSql() {
    if (!sqlDraft.trim()) {
      setError("Write a SELECT query first.");
      return;
    }
    setRunning(true);
    setError("");
    setSummary(null);
    setSummaryError("");
    try {
      const data = await api("/api/query/run", {
        method: "POST",
        body: JSON.stringify({ connection_id: activeId, sql: sqlDraft }),
      });
      setResult(data);
      setSqlDraft(data.sql);
      setSort({ key: null, dir: "asc" });
      setTab("table");
      const rows = await api(`/api/history?connection_id=${encodeURIComponent(activeId)}`);
      setHistory(rows);
      if (autoSummarize && data.rows && data.rows.length) {
        requestSummary(data);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setRunning(false);
    }
  }

  async function removeConnection() {
    if (!active || active.builtin) return;
    if (!window.confirm(`Remove ${active.name}?`)) return;
    try {
      await api(`/api/connections/${active.id}`, { method: "DELETE" });
      setResult(null);
      setActiveId("demo");
      await refreshConnections("demo");
    } catch (err) {
      setError(err.message);
    }
  }

  async function removeHistory(id) {
    try {
      await api(`/api/history/${id}`, { method: "DELETE" });
      setHistory((current) => current.filter((item) => item.id !== id));
    } catch (err) {
      setError(err.message);
    }
  }

  function useHistory(item) {
    if (item.question !== "Manual SQL") setQuestion(item.question);
    setSqlDraft(item.sql || "");
    setTab("sql");
    setHistoryOpen(false);
    setError(item.success ? "" : item.error || "");
    if (item.summary) {
      setSummary(item.summary);
      setSummaryError("");
    } else {
      setSummary(null);
      setSummaryError("");
    }
  }

  function insertColumn(table, column) {
    const token = `${table}.${column}`;
    setQuestion((current) => (current.trim() ? `${current.trim()} ${token}` : `Show ${token}`));
  }

  function exportCsv() {
    if (!result) return;
    download("askdb-results.csv", toCsv(result.columns, result.rows), "text/csv");
  }

  function exportJson() {
    if (!result) return;
    download("askdb-results.json", JSON.stringify(result.rows, null, 2), "application/json");
  }

  async function copySql() {
    const text = result?.sql || sqlDraft;
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      setError("Could not copy the SQL. Select it from the SQL tab instead.");
    }
  }

  return (
    <div className="studio">
      <header className="topbar">
        <div className="brand-lockup">
          <span className="mark">A</span>
          <div>
            <strong>AskDB</strong>
            <p>{health?.model ? `Gemini · ${health.model}` : "Gemini"}</p>
          </div>
        </div>
        <label className="connection-picker">
          <span>Database</span>
          <select value={activeId} onChange={(event) => setActiveId(event.target.value)}>
            {connections.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        <div className="top-actions">
          <button type="button" className="button button-ghost" onClick={() => setConnectOpen(true)}>
            Add database
          </button>
          <button type="button" className="button button-ghost" onClick={() => setHistoryOpen(true)}>
            History
          </button>
          <div className="user-chip">
            <span>{user?.name}</span>
            <button type="button" className="text-button light" onClick={logout}>
              Sign out
            </button>
          </div>
        </div>
      </header>

      {health && !health.gemini_configured ? (
        <p className="banner banner-warn page-banner">
          Gemini is not configured. Add <code>GEMINI_API_KEY</code> to <code>.env</code> and run{" "}
          <code>docker compose up --build</code> again. You can still browse the schema and run SQL yourself.
        </p>
      ) : null}

      <div className="workspace">
        <aside className="schema-pane">
          <div className="schema-head">
            <div>
              <h2>Schema</h2>
              <p>{schema ? `${schema.dialect} · ${schema.tables.length} tables` : "Loading schema…"}</p>
            </div>
            {active && !active.builtin ? (
              <button type="button" className="text-button danger" onClick={removeConnection}>
                Remove
              </button>
            ) : null}
          </div>
          {schemaError ? <p className="banner banner-danger">{schemaError}</p> : null}
          {schema?.note ? <p className="hint">{schema.note}</p> : null}
          <div className="schema-list">
            {(schema?.tables || []).map((table) => (
              <details key={table.name} className="table-block">
                <summary>{table.name}</summary>
                <ul>
                  {table.columns.map((column) => (
                    <li key={column.name}>
                      <button type="button" onClick={() => insertColumn(table.name, column.name)}>
                        <span>{column.name}</span>
                        <small>
                          {column.type}
                          {column.primary_key ? " · pk" : ""}
                        </small>
                      </button>
                    </li>
                  ))}
                </ul>
                {table.foreign_keys.length ? (
                  <p className="fk">
                    {table.foreign_keys.map((fk) => `${fk.column} → ${fk.ref_table}.${fk.ref_column}`).join(" · ")}
                  </p>
                ) : null}
              </details>
            ))}
          </div>
        </aside>

        <main className="canvas">
          <form className="ask-form" onSubmit={onAsk}>
            <label htmlFor="question">Ask a question</label>
            <textarea
              id="question"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="What are the top 5 products by paid revenue?"
              rows={3}
            />
            <div className="ask-actions">
              <button className="button" type="submit" disabled={asking || !question.trim()}>
                {asking ? "Writing SQL…" : "Ask Gemini"}
              </button>
              <button type="button" className="button button-ghost" onClick={copySql} disabled={!result && !sqlDraft}>
                Copy SQL
              </button>
            </div>
          </form>
          <div className="suggestions">
            {(schema?.suggestions || []).map((item) => (
              <button key={item} type="button" className="chip" onClick={() => setQuestion(item)}>
                {item}
              </button>
            ))}
          </div>
          {error ? (
            <p className="banner banner-danger" role="alert">
              {error}
            </p>
          ) : null}

          <details className="manual-sql">
            <summary>Run SQL directly</summary>
            <textarea value={sqlDraft} onChange={(event) => setSqlDraft(event.target.value)} rows={6} spellCheck={false} />
            <button type="button" className="button" onClick={onRunSql} disabled={running}>
              {running ? "Running…" : "Run read-only SQL"}
            </button>
          </details>

          {result ? (
            <section className="result">
              <div className="result-meta">
                <span>{result.row_count} rows</span>
                <span>{result.elapsed_ms} ms</span>
                <span>Confidence {Math.round(result.confidence * 100)}%</span>
                {result.repaired ? <span>Query was corrected once</span> : null}
                {result.truncated ? <span>Capped at {result.row_count} rows</span> : null}
                {result.tables_used?.length ? <span>Tables: {result.tables_used.join(", ")}</span> : null}
              </div>

              <div className="insights-card">
                <div className="insights-card-header">
                  <div className="insights-title">
                    <span>✨</span>
                    <span>Executive Insights</span>
                  </div>
                  <div className="insights-actions">
                    <label className="auto-toggle">
                      <input
                        type="checkbox"
                        checked={autoSummarize}
                        onChange={(e) => toggleAutoSummarize(e.target.checked)}
                      />
                      <span>Auto-summarize</span>
                    </label>
                    {!summary && !summarizing ? (
                      <button
                        type="button"
                        className="btn-generate-insights"
                        onClick={() => requestSummary(result)}
                        disabled={!result.rows || result.rows.length === 0}
                      >
                        ✨ Generate Insights
                      </button>
                    ) : null}
                  </div>
                </div>

                {summarizing ? (
                  <div className="insights-loading">
                    <div className="insights-spinner" />
                    <span>Analyzing data patterns and identifying takeaways…</span>
                  </div>
                ) : null}

                {summaryError ? (
                  <div className="insights-error">
                    <span>{summaryError}</span>
                    <button
                      type="button"
                      className="text-button"
                      onClick={() => requestSummary(result)}
                    >
                      Retry
                    </button>
                  </div>
                ) : null}

                {!summary && !summarizing && !summaryError && (!result.rows || result.rows.length === 0) ? (
                  <p className="muted" style={{ margin: 0, fontSize: "0.88rem" }}>
                    Query returned zero rows. Run a query that returns data to generate insights.
                  </p>
                ) : null}

                {summary && !summarizing ? (
                  <>
                    <div className="insights-headline">
                      <span className="badge">Key Takeaway</span>
                      {summary.headline}
                    </div>

                    {summary.key_findings?.length ? (
                      <ul className="insights-bullets">
                        {summary.key_findings.map((point, index) => (
                          <li key={index}>{point}</li>
                        ))}
                      </ul>
                    ) : null}

                    {summary.anomalies?.length &&
                    summary.anomalies.some(
                      (a) =>
                        a &&
                        !a.toLowerCase().includes("none detected") &&
                        !a.toLowerCase().includes("no anomalies"),
                    ) ? (
                      <div className="insights-anomalies">
                        <strong>Notice:</strong>
                        {summary.anomalies.join(" • ")}
                      </div>
                    ) : null}

                    {summary.follow_up_questions?.length ? (
                      <div className="insights-followups">
                        <span className="followups-label">Suggested Next Questions:</span>
                        <div className="followups-chips">
                          {summary.follow_up_questions.map((q, index) => (
                            <button
                              key={index}
                              type="button"
                              className="followup-chip"
                              onClick={() => selectFollowUp(q)}
                              title="Click to place in question input"
                            >
                              <span>{q}</span>
                              <span style={{ opacity: 0.6 }}>↗</span>
                            </button>
                          ))}
                        </div>
                      </div>
                    ) : null}
                  </>
                ) : null}
              </div>

              <div className="tabs">
                {["table", "chart", "sql", "reasoning", "stats"].map((name) => (
                  <button
                    key={name}
                    type="button"
                    className={tab === name ? "tab active" : "tab"}
                    onClick={() => setTab(name)}
                  >
                    {name}
                  </button>
                ))}
                <span className="tab-spacer" />
                <button type="button" className="text-button" onClick={exportCsv}>
                  CSV
                </button>
                <button type="button" className="text-button" onClick={exportJson}>
                  JSON
                </button>
              </div>

              {tab === "table" ? (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        {result.columns.map((column) => (
                          <th key={column}>
                            <button type="button" onClick={() => toggleSort(column)}>
                              {column}
                              {sort.key === column ? (sort.dir === "asc" ? " ↑" : " ↓") : ""}
                            </button>
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {visibleRows.length ? (
                        visibleRows.map((row, index) => (
                          <tr key={index}>
                            {result.columns.map((column) => (
                              <td key={column}>{row[column] == null ? "—" : String(row[column])}</td>
                            ))}
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={result.columns.length || 1}>The query returned no rows.</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              ) : null}

              {tab === "chart" ? (
                <ChartView
                  rows={result.rows}
                  columns={result.columns}
                  chart={result.chart}
                  xColumn={result.x_column}
                  yColumn={result.y_column}
                />
              ) : null}

              {tab === "sql" ? <SqlBlock sql={result.sql} /> : null}

              {tab === "reasoning" ? <p className="reasoning">{result.reasoning || "No reasoning was returned."}</p> : null}

              {tab === "stats" ? (
                <div className="stats-grid">
                  {result.stats.map((item) => (
                    <article key={item.column} className="stat-card">
                      <h3>{item.column}</h3>
                      <p>{item.kind}</p>
                      <dl>
                        <div>
                          <dt>Count</dt>
                          <dd>{item.count}</dd>
                        </div>
                        <div>
                          <dt>Nulls</dt>
                          <dd>{item.nulls}</dd>
                        </div>
                        <div>
                          <dt>Distinct</dt>
                          <dd>{item.distinct}</dd>
                        </div>
                        {item.kind === "number" ? (
                          <>
                            <div>
                              <dt>Min</dt>
                              <dd>{item.min}</dd>
                            </div>
                            <div>
                              <dt>Max</dt>
                              <dd>{item.max}</dd>
                            </div>
                            <div>
                              <dt>Mean</dt>
                              <dd>{item.mean}</dd>
                            </div>
                          </>
                        ) : (
                          <div>
                            <dt>Top</dt>
                            <dd>{item.top || "—"}</dd>
                          </div>
                        )}
                      </dl>
                    </article>
                  ))}
                </div>
              ) : null}
            </section>
          ) : (
            <section className="empty-state">
              <h2>{active?.builtin ? "Harbor & Co. is loaded." : `${active?.name || "This database"} is ready.`}</h2>
              <p>
                {active?.builtin
                  ? "Four stores, a product list, and a year of orders are ready. Ask about revenue, stock, regions, or employees."
                  : "Ask a question in plain language, or open a table in the schema and run a SELECT yourself."}{" "}
                Every query is checked and executed read-only.
              </p>
            </section>
          )}
        </main>
      </div>

      {connectOpen ? (
        <ConnectModal
          onClose={() => setConnectOpen(false)}
          onCreated={async (created) => {
            setConnectOpen(false);
            await refreshConnections(created.id);
          }}
        />
      ) : null}

      {historyOpen ? (
        <div className="drawer-backdrop" onClick={() => setHistoryOpen(false)}>
          <aside className="drawer" onClick={(event) => event.stopPropagation()} aria-label="Query history">
            <div className="modal-head">
              <h2>History</h2>
              <button type="button" className="text-button" onClick={() => setHistoryOpen(false)}>
                Close
              </button>
            </div>
            {history.length ? (
              <ul className="history-list">
                {history.map((item) => (
                  <li key={item.id} className={item.success ? "" : "failed"}>
                    <button type="button" className="history-main" onClick={() => useHistory(item)}>
                      <strong>{item.question}</strong>
                      <span>
                        {formatWhen(item.created_at)}
                        {item.row_count != null ? ` · ${item.row_count} rows` : ""}
                        {item.summary ? " · ✨ Insights" : ""}
                        {item.success ? "" : " · failed"}
                      </span>
                    </button>
                    <button type="button" className="text-button danger" onClick={() => removeHistory(item.id)}>
                      Delete
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">Questions you ask on this database will show up here.</p>
            )}
          </aside>
        </div>
      ) : null}
    </div>
  );
}
