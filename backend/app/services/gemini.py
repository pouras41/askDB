import json
import re
from datetime import date

import httpx

from app.config import settings

class GeminiError(RuntimeError):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


_CHARTS = {"bar", "line", "scatter", "area", "histogram", "pie", "table"}

_SUMMARY_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "headline": {"type": "STRING"},
        "key_findings": {"type": "ARRAY", "items": {"type": "STRING"}},
        "anomalies": {"type": "ARRAY", "items": {"type": "STRING"}},
        "follow_up_questions": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
    "required": ["headline", "key_findings", "anomalies", "follow_up_questions"],
}

_SUMMARY_SYSTEM = """You are an expert executive data analyst. You analyze SQL query results and extract actionable, clear business insights for decision-makers.

Return a single JSON object with these fields:
- headline: A single punchy, high-level takeaway summarizing the most important finding (1 sentence).
- key_findings: 3 to 4 concise bullet points explaining rankings, proportions, key comparisons, or trends. Include concrete numbers or names from the results.
- anomalies: 1 to 2 bullet points highlighting any outliers, unexpected zeros, sudden drops, or note that no anomalies were detected.
- follow_up_questions: 3 logical next questions the user should ask to drill deeper into the data. Keep them concise and phrased naturally as direct questions.

Rules:
- Be factual and derive all findings strictly from the provided data and column statistics.
- Never invent numbers, columns, or patterns not supported by the data.
- Avoid technical SQL jargon in the headline and key findings (e.g. use 'customers' instead of 'rows', 'sales' instead of 'sum(quantity * unit_price)').
"""

_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "sql": {"type": "STRING"},
        "reasoning": {"type": "STRING"},
        "confidence": {"type": "NUMBER"},
        "tables_used": {"type": "ARRAY", "items": {"type": "STRING"}},
        "chart": {"type": "STRING"},
        "x_column": {"type": "STRING"},
        "y_column": {"type": "STRING"},
        "error": {"type": "STRING"},
    },
    "required": ["sql", "reasoning", "confidence", "tables_used", "chart"],
}

_SYSTEM = """You translate one natural-language question into one read-only SQL query.

Return a single JSON object with these fields:
- sql: one SELECT or WITH statement. Empty when the question cannot be answered.
- reasoning: a short explanation of the tables, joins, filters, and chart choice.
- confidence: a number from 0 to 1.
- tables_used: table names referenced by the query.
- chart: one of bar, line, scatter, area, histogram, pie, table.
- x_column: the category, time, or x-axis column alias in the SELECT list. Empty if none.
- y_column: the numeric measure column alias in the SELECT list. Empty if none.
- error: empty when sql is usable, otherwise a short reason.

Rules:
- Use only tables and columns that appear in the schema.
- Use the requested SQL dialect.
- Use explicit JOIN ... ON. Follow foreign keys. Do not invent relationships.
- Never write INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE, COPY, GRANT, or more than one statement.
- Alias aggregated expressions with clear names such as revenue, order_count, or month.
- Chart choice: bar compares categories, line and area show a trend, scatter compares two numbers, histogram is one numeric distribution, pie is a share of a whole with few categories, table is for raw rows.
- If the question is ambiguous, choose the most useful reading and say so in reasoning.
"""


def parse_model_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            raise GeminiError("Gemini returned a response that was not valid JSON.")
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise GeminiError("Gemini returned a response that was not valid JSON.") from exc
    if not isinstance(data, dict):
        raise GeminiError("Gemini returned an unexpected response.")
    return normalize_plan(data)


def normalize_plan(data: dict) -> dict:
    sql = str(data.get("sql") or "").strip()
    reasoning = str(data.get("reasoning") or "").strip()
    error = str(data.get("error") or "").strip()
    chart = str(data.get("chart") or "table").strip().lower()
    if chart not in _CHARTS:
        chart = "table"
    try:
        confidence = float(data.get("confidence") or 0)
    except (TypeError, ValueError):
        confidence = 0
    if confidence > 1:
        confidence = confidence / 10 if confidence <= 10 else 1
    confidence = max(0.0, min(confidence, 1.0))
    tables = data.get("tables_used") or []
    if not isinstance(tables, list):
        tables = []
    x_column = str(data.get("x_column") or "").strip() or None
    y_column = str(data.get("y_column") or "").strip() or None
    return {
        "sql": sql,
        "reasoning": reasoning,
        "confidence": confidence,
        "tables_used": [str(item) for item in tables if str(item).strip()],
        "chart": chart,
        "x_column": x_column,
        "y_column": y_column,
        "error": error,
    }


def parse_summary_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            raise GeminiError("Gemini returned an insight response that was not valid JSON.")
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise GeminiError("Gemini returned an insight response that was not valid JSON.") from exc
    if not isinstance(data, dict):
        raise GeminiError("Gemini returned an unexpected insight response format.")
    return normalize_summary(data)


def normalize_summary(data: dict) -> dict:
    headline = str(data.get("headline") or "").strip()
    if not headline:
        headline = "Analysis of query results completed."
    raw_findings = data.get("key_findings") or []
    if isinstance(raw_findings, list):
        findings = [str(item).strip() for item in raw_findings if str(item).strip()]
    else:
        findings = [str(raw_findings).strip()] if str(raw_findings).strip() else []
    if not findings:
        findings = ["Data retrieved successfully."]

    raw_anomalies = data.get("anomalies") or []
    if isinstance(raw_anomalies, list):
        anomalies = [str(item).strip() for item in raw_anomalies if str(item).strip()]
    else:
        anomalies = [str(raw_anomalies).strip()] if str(raw_anomalies).strip() else []

    raw_follow_ups = data.get("follow_up_questions") or []
    if isinstance(raw_follow_ups, list):
        follow_ups = [str(item).strip() for item in raw_follow_ups if str(item).strip()]
    else:
        follow_ups = [str(raw_follow_ups).strip()] if str(raw_follow_ups).strip() else []

    return {
        "headline": headline,
        "key_findings": findings[:5],
        "anomalies": anomalies[:3],
        "follow_up_questions": follow_ups[:4],
    }


def condense_rows(rows: list[dict], max_rows: int = 20) -> list[dict]:
    if len(rows) <= max_rows:
        return rows
    half = max_rows // 2
    return rows[:half] + rows[-half:]


def build_summary_prompt(
    question: str,
    sql: str,
    columns: list[str],
    sample_rows: list[dict],
    stats: list[dict],
    total_row_count: int,
) -> str:
    parts = [
        f"User Question: {question}",
        f"Executed SQL: {sql}",
        f"Columns ({len(columns)}): {', '.join(columns)}",
        f"Total Rows Count: {total_row_count}",
        "Column Summary Statistics:",
        json.dumps(stats, default=str),
        f"Sample Data Rows ({len(sample_rows)} rows):",
        json.dumps(sample_rows, default=str),
    ]
    return "\n\n".join(parts)


def generate_summary(
    question: str,
    sql: str,
    columns: list[str],
    rows: list[dict],
    stats: list[dict],
) -> dict:
    if not settings.gemini_api_key.strip():
        raise GeminiError(
            "GEMINI_API_KEY is not set. Add a free key from Google AI Studio to the .env file and run docker compose up again.",
            status_code=503,
        )

    sample_rows = condense_rows(rows, max_rows=20)
    prompt = build_summary_prompt(
        question=question,
        sql=sql,
        columns=columns,
        sample_rows=sample_rows,
        stats=stats,
        total_row_count=len(rows),
    )
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_model}:generateContent"
    )
    base_body = {
        "systemInstruction": {"parts": [{"text": _SUMMARY_SYSTEM}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
    }
    structured = {
        **base_body,
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
            "responseSchema": _SUMMARY_RESPONSE_SCHEMA,
        },
    }
    plain = {
        **base_body,
        "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
    }

    text = _post(url, structured, allow_schema_retry=True, plain_body=plain)
    return parse_summary_json(text)


def _schema_payload(schema: dict) -> dict:
    tables = []
    for table in schema.get("tables", [])[:30]:
        tables.append(
            {
                "name": table["name"],
                "columns": [
                    {
                        "name": column["name"],
                        "type": column["type"],
                        "primary_key": column["primary_key"],
                    }
                    for column in table["columns"]
                ],
                "foreign_keys": table["foreign_keys"],
                "sample_rows": table["sample_rows"][:2],
            }
        )
    return {"dialect": schema.get("dialect"), "tables": tables, "truncated": len(schema.get("tables", [])) > 30}


def build_user_prompt(
    question: str,
    schema: dict,
    dialect: str,
    note: str,
    previous_sql: str | None = None,
    previous_error: str | None = None,
) -> str:
    parts = [
        f"Dialect: {dialect}",
        f"Today: {date.today().isoformat()}",
    ]
    if note:
        parts.append(f"Dataset note: {note}")
    parts.append("Schema JSON:")
    parts.append(json.dumps(_schema_payload(schema), default=str))
    parts.append(f"Question: {question}")
    if previous_sql or previous_error:
        parts.append("The previous query failed. Write a corrected query.")
        parts.append(f"Previous SQL: {previous_sql or ''}")
        parts.append(f"Database or validator error: {previous_error or ''}")
    return "\n\n".join(parts)


def _extract_text(payload: dict) -> str:
    candidates = payload.get("candidates") or []
    if not candidates:
        message = payload.get("error", {}).get("message") if isinstance(payload.get("error"), dict) else None
        raise GeminiError(message or "Gemini did not return a query. Try rephrasing the question.")
    parts = ((candidates[0].get("content") or {}).get("parts")) or []
    texts = [part.get("text", "") for part in parts if isinstance(part, dict) and part.get("text")]
    if not texts:
        raise GeminiError("Gemini returned an empty response. Try rephrasing the question.")
    return "\n".join(texts)


def generate_sql(
    question: str,
    schema: dict,
    dialect: str,
    note: str = "",
    previous_sql: str | None = None,
    previous_error: str | None = None,
) -> dict:
    if not settings.gemini_api_key.strip():
        raise GeminiError(
            "GEMINI_API_KEY is not set. Add a free key from Google AI Studio to the .env file and run docker compose up again.",
            status_code=503,
        )

    prompt = build_user_prompt(question, schema, dialect, note, previous_sql, previous_error)
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_model}:generateContent"
    )
    base_body = {
        "systemInstruction": {"parts": [{"text": _SYSTEM}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
    }
    structured = {
        **base_body,
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
            "responseSchema": _RESPONSE_SCHEMA,
        },
    }
    plain = {
        **base_body,
        "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
    }

    text = _post(url, structured, allow_schema_retry=True, plain_body=plain)
    plan = parse_model_json(text)
    if plan["error"] and not plan["sql"]:
        raise GeminiError(plan["error"], status_code=422)
    if not plan["sql"]:
        raise GeminiError(plan["error"] or "Gemini did not return a SQL query.", status_code=422)
    return plan


def _post(url: str, body: dict, allow_schema_retry: bool = False, plain_body: dict | None = None) -> str:
    headers = {"x-goog-api-key": settings.gemini_api_key, "Content-Type": "application/json"}
    try:
        with httpx.Client(timeout=60) as client:
            response = client.post(url, headers=headers, json=body)
    except httpx.HTTPError as exc:
        raise GeminiError("Could not reach the Gemini API. Check your network and try again.") from exc

    if response.status_code == 429:
        raise GeminiError(
            "The Gemini free-tier rate limit was hit. Wait a minute and try again.",
            status_code=429,
        )
    if response.status_code == 400 and allow_schema_retry and plain_body is not None:
        return _post(url, plain_body)
    if response.status_code >= 400:
        detail = _safe_error(response)
        if response.status_code == 404:
            raise GeminiError(
                f"Gemini model '{settings.gemini_model}' was not found. Set GEMINI_MODEL to gemini-3.5-flash-lite or gemini-3.8-flash. {detail}",
                status_code=502,
            )
        raise GeminiError(f"Gemini request failed ({response.status_code}). {detail}", status_code=502)
    try:
        payload = response.json()
    except json.JSONDecodeError as exc:
        raise GeminiError("Gemini returned a response that was not JSON.") from exc
    return _extract_text(payload)


def _safe_error(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except json.JSONDecodeError:
        return response.text[:240]
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])[:300]
    return ""
