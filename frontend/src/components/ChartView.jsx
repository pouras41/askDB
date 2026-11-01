import { useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const COLORS = ["#1f6b4a", "#b64b24", "#1d4e89", "#a16207", "#6b3fa0", "#0f766e", "#9f2d2d", "#3f6212"];
const KINDS = ["bar", "line", "area", "scatter", "histogram", "pie", "table"];

function asNumber(value) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const number = Number(value);
    if (Number.isFinite(number)) return number;
  }
  return null;
}

function histogram(rows, column) {
  const values = rows.map((row) => asNumber(row[column])).filter((value) => value != null);
  if (!values.length) return [];
  const min = Math.min(...values);
  const max = Math.max(...values);
  const bins = 8;
  const span = max - min || 1;
  const counts = Array.from({ length: bins }, (_, index) => {
    const start = min + (span * index) / bins;
    const end = min + (span * (index + 1)) / bins;
    return { label: `${start.toFixed(0)}–${end.toFixed(0)}`, count: 0 };
  });
  for (const value of values) {
    let index = Math.floor(((value - min) / span) * bins);
    if (index >= bins) index = bins - 1;
    if (index < 0) index = 0;
    counts[index].count += 1;
  }
  return counts;
}

function pieSlices(rows, nameKey, valueKey) {
  const totals = new Map();
  for (const row of rows) {
    const amount = asNumber(row[valueKey]);
    if (amount == null) continue;
    const name = row[nameKey] == null ? "Unknown" : String(row[nameKey]);
    totals.set(name, (totals.get(name) || 0) + amount);
  }
  const sorted = [...totals.entries()].sort((a, b) => b[1] - a[1]);
  const head = sorted.slice(0, 7).map(([name, value]) => ({ name, value }));
  const rest = sorted.slice(7).reduce((sum, [, value]) => sum + value, 0);
  if (rest > 0) head.push({ name: "Other", value: rest });
  return head;
}

export default function ChartView({ rows, columns, chart, xColumn, yColumn }) {
  const [kind, setKind] = useState(chart || "bar");
  const [x, setX] = useState(xColumn || columns[0] || "");
  const [y, setY] = useState(yColumn || columns[1] || columns[0] || "");

  useEffect(() => {
    setKind(chart && chart !== "table" ? chart : "bar");
    setX(xColumn || columns[0] || "");
    setY(yColumn || columns.find((column) => column !== xColumn) || columns[0] || "");
  }, [chart, xColumn, yColumn, columns]);

  const scatterData = useMemo(
    () =>
      rows
        .map((row) => ({ x: asNumber(row[x]), y: asNumber(row[y]) }))
        .filter((point) => point.x != null && point.y != null),
    [rows, x, y],
  );

  const axisData = useMemo(
    () => rows.map((row) => ({ ...row, [y]: asNumber(row[y]) ?? row[y] })),
    [rows, y],
  );

  let body = <p className="muted">Choose columns to draw this chart.</p>;
  if (!rows.length) {
    body = <p className="muted">This result has no rows to chart.</p>;
  } else if (kind === "histogram") {
    const data = histogram(rows, y || x);
    body = data.length ? (
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data}>
          <CartesianGrid stroke="#e4dccf" vertical={false} />
          <XAxis dataKey="label" tick={{ fill: "#24312a", fontSize: 12 }} />
          <YAxis allowDecimals={false} tick={{ fill: "#24312a", fontSize: 12 }} />
          <Tooltip />
          <Bar dataKey="count" fill="#1f6b4a" radius={[6, 6, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    ) : (
      <p className="muted">Pick a numeric column for the histogram.</p>
    );
  } else if (kind === "pie") {
    const data = pieSlices(rows, x, y);
    body = data.length ? (
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="name" outerRadius={120}>
            {data.map((entry, index) => (
              <Cell key={entry.name} fill={COLORS[index % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip />
        </PieChart>
      </ResponsiveContainer>
    ) : (
      <p className="muted">A pie chart needs a category and a number.</p>
    );
  } else if (kind === "scatter") {
    body = scatterData.length ? (
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart>
          <CartesianGrid stroke="#e4dccf" />
          <XAxis dataKey="x" name={x} tick={{ fill: "#24312a", fontSize: 12 }} />
          <YAxis dataKey="y" name={y} tick={{ fill: "#24312a", fontSize: 12 }} />
          <Tooltip />
          <Scatter data={scatterData} fill="#b64b24" />
        </ScatterChart>
      </ResponsiveContainer>
    ) : (
      <p className="muted">A scatter plot needs two numeric columns.</p>
    );
  } else if (kind === "line" || kind === "area") {
    const Chart = kind === "line" ? LineChart : AreaChart;
    const Mark = kind === "line" ? Line : Area;
    body = (
      <ResponsiveContainer width="100%" height="100%">
        <Chart data={axisData}>
          <CartesianGrid stroke="#e4dccf" vertical={false} />
          <XAxis dataKey={x} tick={{ fill: "#24312a", fontSize: 12 }} />
          <YAxis tick={{ fill: "#24312a", fontSize: 12 }} />
          <Tooltip />
          <Mark type="monotone" dataKey={y} stroke="#1f6b4a" fill="#1f6b4a" fillOpacity={0.25} strokeWidth={2} />
        </Chart>
      </ResponsiveContainer>
    );
  } else if (kind === "bar") {
    body = (
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={axisData}>
          <CartesianGrid stroke="#e4dccf" vertical={false} />
          <XAxis dataKey={x} tick={{ fill: "#24312a", fontSize: 12 }} />
          <YAxis tick={{ fill: "#24312a", fontSize: 12 }} />
          <Tooltip />
          <Bar dataKey={y} fill="#1d4e89" radius={[6, 6, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    );
  }

  return (
    <div className="chart-panel">
      <div className="chart-controls">
        <label>
          Chart
          <select value={kind} onChange={(event) => setKind(event.target.value)}>
            {KINDS.filter((item) => item !== "table").map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>
        <label>
          X
          <select value={x} onChange={(event) => setX(event.target.value)}>
            {columns.map((column) => (
              <option key={column} value={column}>
                {column}
              </option>
            ))}
          </select>
        </label>
        <label>
          Y
          <select value={y} onChange={(event) => setY(event.target.value)}>
            {columns.map((column) => (
              <option key={column} value={column}>
                {column}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="chart-frame">{body}</div>
    </div>
  );
}
