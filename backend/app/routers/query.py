import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.deps import get_current_user
from app.limiter import enforce_rate_limit
from app.models import QueryHistory, User
from app.schemas import (
    AskRequest,
    HistoryItem,
    InsightSummary,
    QueryResponse,
    RunSqlRequest,
    SummarizeRequest,
)
from app.services.gemini import GeminiError, generate_summary
from app.services.query import answer_question, enforce_daily_limit, run_manual_sql

router = APIRouter(prefix="/api", tags=["query"])


def _client_key(request: Request) -> str:
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _history_item(row: QueryHistory) -> HistoryItem:
    summary = None
    if row.summary_json:
        try:
            summary = InsightSummary.model_validate_json(row.summary_json)
        except Exception:
            summary = None

    return HistoryItem(
        id=row.id,
        connection_ref=row.connection_ref,
        connection_name=row.connection_name,
        question=row.question,
        sql=row.sql_text,
        reasoning=row.reasoning,
        chart=row.chart,
        row_count=row.row_count,
        success=row.success,
        error=row.error,
        elapsed_ms=row.elapsed_ms,
        created_at=row.created_at,
        summary=summary,
    )


@router.post("/query", response_model=QueryResponse)
def ask(
    payload: AskRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QueryResponse:
    enforce_rate_limit(
        f"query:{user.id}",
        settings.query_rate_limit,
        settings.query_rate_window_seconds,
    )
    enforce_rate_limit(f"query-ip:{_client_key(request)}", settings.query_rate_limit, settings.query_rate_window_seconds)
    enforce_daily_limit(db, user.id)
    return answer_question(db, user, payload.connection_id, payload.question.strip())


@router.post("/query/run", response_model=QueryResponse)
def run_sql(
    payload: RunSqlRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QueryResponse:
    enforce_rate_limit(f"sql:{user.id}", 30, settings.query_rate_window_seconds)
    return run_manual_sql(db, user, payload.connection_id, payload.sql)


@router.get("/history", response_model=list[HistoryItem])
def history(
    connection_id: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[HistoryItem]:
    stmt = select(QueryHistory).where(QueryHistory.user_id == user.id)
    if connection_id:
        stmt = stmt.where(QueryHistory.connection_ref == connection_id)
    rows = db.scalars(stmt.order_by(QueryHistory.created_at.desc()).limit(50)).all()
    return [_history_item(row) for row in rows]


@router.delete("/history/{history_id}", status_code=204)
def delete_history(
    history_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    row = db.scalar(
        select(QueryHistory).where(QueryHistory.id == history_id, QueryHistory.user_id == user.id)
    )
    if row is None:
        raise HTTPException(status_code=404, detail="That history item was not found.")
    db.delete(row)
    db.commit()


@router.post("/query/{history_id}/summarize", response_model=InsightSummary)
def summarize_query(
    history_id: uuid.UUID,
    payload: SummarizeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InsightSummary:
    row = db.scalar(
        select(QueryHistory).where(QueryHistory.id == history_id, QueryHistory.user_id == user.id)
    )
    if row is None:
        raise HTTPException(status_code=404, detail="That query was not found.")

    if row.summary_json:
        try:
            return InsightSummary.model_validate_json(row.summary_json)
        except Exception:
            pass

    enforce_rate_limit(
        f"summary:{user.id}",
        settings.query_rate_limit,
        settings.query_rate_window_seconds,
    )
    enforce_daily_limit(db, user.id)

    try:
        stats_dicts = [s.model_dump() for s in payload.stats]
        insight_dict = generate_summary(
            question=row.question,
            sql=row.sql_text or "",
            columns=payload.columns,
            rows=payload.rows,
            stats=stats_dicts,
        )
        insight = InsightSummary(**insight_dict)
        row.summary_json = insight.model_dump_json()
        row.used_model = True
        db.commit()
        return insight
    except GeminiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not generate insights: {exc}") from exc
