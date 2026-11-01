import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserPublic(BaseModel):
    id: uuid.UUID
    name: str
    email: EmailStr


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=10)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=10)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserPublic


class PostgresConnectionRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=5432, ge=1, le=65535)
    database: str = Field(min_length=1, max_length=255)
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=500)


class ConnectionPublic(BaseModel):
    id: str
    name: str
    kind: str
    detail: str
    builtin: bool


class ColumnInfo(BaseModel):
    name: str
    type: str
    nullable: bool
    primary_key: bool


class ForeignKeyInfo(BaseModel):
    column: str
    ref_table: str
    ref_column: str


class TableInfo(BaseModel):
    name: str
    columns: list[ColumnInfo]
    foreign_keys: list[ForeignKeyInfo]
    sample_rows: list[dict]


class SchemaResponse(BaseModel):
    dialect: str
    name: str
    tables: list[TableInfo]
    suggestions: list[str]
    note: str | None = None


class AskRequest(BaseModel):
    connection_id: str = Field(min_length=1, max_length=64)
    question: str = Field(min_length=3, max_length=2000)


class RunSqlRequest(BaseModel):
    connection_id: str = Field(min_length=1, max_length=64)
    sql: str = Field(min_length=1, max_length=8000)


class ColumnStat(BaseModel):
    column: str
    kind: str
    count: int
    nulls: int
    distinct: int | None = None
    min: str | None = None
    max: str | None = None
    mean: float | None = None
    top: str | None = None


class InsightSummary(BaseModel):
    headline: str
    key_findings: list[str] = []
    anomalies: list[str] = []
    follow_up_questions: list[str] = []


class SummarizeRequest(BaseModel):
    columns: list[str] = []
    rows: list[dict] = []
    stats: list[ColumnStat] = []


class QueryResponse(BaseModel):
    history_id: uuid.UUID
    sql: str
    reasoning: str
    confidence: float
    tables_used: list[str]
    chart: str
    x_column: str | None
    y_column: str | None
    columns: list[str]
    rows: list[dict]
    stats: list[ColumnStat]
    row_count: int
    truncated: bool
    elapsed_ms: int
    repaired: bool
    summary: InsightSummary | None = None


class HistoryItem(BaseModel):
    id: uuid.UUID
    connection_ref: str
    connection_name: str
    question: str
    sql: str | None
    reasoning: str | None
    chart: str | None
    row_count: int | None
    success: bool
    error: str | None
    elapsed_ms: int | None
    created_at: datetime
    summary: InsightSummary | None = None
