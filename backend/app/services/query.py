import time
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import QueryHistory, SavedConnection, User
from app.schemas import QueryResponse
from app.services.database import (
    DEMO_ID,
    DatabaseError,
    execute_select,
    introspect,
    dataset_note,
    resolve_target,
)
from app.services.gemini import GeminiError, generate_sql
from app.services.sql_guard import SqlGuardError, guard_sql
from app.services.stats import summarize


def enforce_daily_limit(db: Session, user_id: uuid.UUID) -> None:
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    count = db.scalar(
        select(func.count())
        .select_from(QueryHistory)
        .where(
            QueryHistory.user_id == user_id,
            QueryHistory.created_at >= start,
            QueryHistory.used_model.is_(True),
        )
    )
    if count is not None and count >= settings.query_daily_limit:
        raise HTTPException(
            status_code=429,
            detail="Daily question limit reached. It resets at midnight UTC.",
        )


def load_target(db: Session, user: User, connection_id: str):
    if connection_id == DEMO_ID:
        return resolve_target(None, DEMO_ID)
    try:
        connection_uuid = uuid.UUID(connection_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="That connection was not found.") from exc
    connection = db.scalar(
        select(SavedConnection).where(
            SavedConnection.id == connection_uuid,
            SavedConnection.user_id == user.id,
        )
    )
    if connection is None:
        raise HTTPException(status_code=404, detail="That connection was not found.")
    try:
        return resolve_target(connection, connection_id)
    except DatabaseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def answer_question(db: Session, user: User, connection_id: str, question: str) -> QueryResponse:
    target = load_target(db, user, connection_id)
    try:
        schema = introspect(target.url, target.dialect)
    except DatabaseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    note = dataset_note(target.builtin)
    started = time.perf_counter()
    repaired = False
    plan: dict | None = None
    try:
        plan = generate_sql(question, schema, target.dialect, note)
        try:
            sql, columns, rows = _run(target.url, target.dialect, plan["sql"])
        except (SqlGuardError, DatabaseError) as first_error:
            repaired = True
            plan = generate_sql(
                question,
                schema,
                target.dialect,
                note,
                previous_sql=plan["sql"],
                previous_error=str(first_error),
            )
            sql, columns, rows = _run(target.url, target.dialect, plan["sql"])
    except (GeminiError, SqlGuardError, DatabaseError) as exc:
        _save(
            db,
            user,
            target,
            question,
            plan["sql"] if plan else None,
            plan["reasoning"] if plan else None,
            plan["chart"] if plan else None,
            None,
            False,
            str(exc),
            _elapsed(started),
            not isinstance(exc, GeminiError) or exc.status_code != 503,
        )
        status = exc.status_code if isinstance(exc, GeminiError) else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc

    return _success(db, user, target, question, plan, sql, columns, rows, _elapsed(started), repaired, True)


def run_manual_sql(db: Session, user: User, connection_id: str, sql_text: str) -> QueryResponse:
    target = load_target(db, user, connection_id)
    started = time.perf_counter()
    try:
        sql, columns, rows = _run(target.url, target.dialect, sql_text)
    except (SqlGuardError, DatabaseError) as exc:
        _save(
            db,
            user,
            target,
            "Manual SQL",
            sql_text,
            None,
            None,
            None,
            False,
            str(exc),
            _elapsed(started),
            False,
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    plan = {
        "sql": sql,
        "reasoning": "Ran the SQL you provided. AskDB checked that it is a single read-only query.",
        "confidence": 1,
        "tables_used": [],
        "chart": "table",
        "x_column": None,
        "y_column": None,
    }
    return _success(db, user, target, "Manual SQL", plan, sql, columns, rows, _elapsed(started), False, False)


def _run(url: str, dialect: str, sql_text: str) -> tuple[str, list[str], list[dict]]:
    sql = guard_sql(sql_text, settings.max_rows)
    columns, rows = execute_select(url, dialect, sql)
    return sql, columns, rows


def _success(
    db: Session,
    user: User,
    target,
    question: str,
    plan: dict,
    sql: str,
    columns: list[str],
    rows: list[dict],
    elapsed_ms: int,
    repaired: bool,
    used_model: bool,
) -> QueryResponse:
    stats = summarize(columns, rows)
    x_column, y_column = _align_chart(plan.get("x_column"), plan.get("y_column"), columns, stats)
    history = _save(
        db,
        user,
        target,
        question,
        sql,
        plan.get("reasoning"),
        plan.get("chart"),
        len(rows),
        True,
        None,
        elapsed_ms,
        used_model,
    )
    return QueryResponse(
        history_id=history.id,
        sql=sql,
        reasoning=str(plan.get("reasoning") or ""),
        confidence=float(plan.get("confidence") or 0),
        tables_used=list(plan.get("tables_used") or []),
        chart=str(plan.get("chart") or "table"),
        x_column=x_column,
        y_column=y_column,
        columns=columns,
        rows=rows,
        stats=stats,
        row_count=len(rows),
        truncated=len(rows) >= settings.max_rows,
        elapsed_ms=elapsed_ms,
        repaired=repaired,
    )


def _save(
    db: Session,
    user: User,
    target,
    question: str,
    sql_text: str | None,
    reasoning: str | None,
    chart: str | None,
    row_count: int | None,
    success: bool,
    error: str | None,
    elapsed_ms: int,
    used_model: bool,
) -> QueryHistory:
    history = QueryHistory(
        user_id=user.id,
        connection_ref=target.ref,
        connection_name=target.name,
        question=question,
        sql_text=sql_text,
        reasoning=reasoning,
        chart=chart,
        row_count=row_count,
        success=success,
        error=error,
        elapsed_ms=elapsed_ms,
        used_model=used_model,
    )
    db.add(history)
    db.commit()
    db.refresh(history)
    return history


def _elapsed(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _align_chart(
    x_column: str | None,
    y_column: str | None,
    columns: list[str],
    stats: list[dict],
) -> tuple[str | None, str | None]:
    lookup = {column.lower(): column for column in columns}
    x_value = lookup.get(x_column.lower()) if x_column else None
    y_value = lookup.get(y_column.lower()) if y_column else None
    numeric = [item["column"] for item in stats if item["kind"] == "number"]
    text = [item["column"] for item in stats if item["kind"] == "text"]
    if x_value is None:
        x_value = (text or columns or [None])[0]
    if y_value is None:
        y_value = next((column for column in numeric if column != x_value), None)
    return x_value, y_value
