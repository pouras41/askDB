import re
import threading
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from urllib.parse import quote_plus

from sqlalchemy import create_engine, event, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.crypto import decrypt_secret
from app.models import SavedConnection

_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_BLOCKED_HOSTS = {"169.254.169.254", "metadata.google.internal"}
_engines: dict[str, Engine] = {}
_engine_lock = threading.Lock()

DEMO_ID = "demo"
DEMO_NAME = "Harbor & Co. demo"
DEMO_NOTE = (
    "Harbor & Co. is a coffee retailer. Revenue is order_items.quantity * order_items.unit_price. "
    "Paid revenue should filter orders.status = 'paid'. Stock lives on products.stock."
)


class DatabaseError(RuntimeError):
    pass


@dataclass
class Target:
    ref: str
    name: str
    kind: str
    dialect: str
    url: str
    builtin: bool


def json_safe(value: object) -> object:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            return None
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")[:200]
    return str(value)


def public_db_error(exc: Exception) -> str:
    message = str(exc).split("\n")[0]
    message = re.sub(r"postgresql\+psycopg://\S+", "postgresql://***", message)
    message = re.sub(r"sqlite:///\S+", "sqlite:///***", message)
    return message[:500] or "The database rejected the query."


def validate_host(host: str) -> str:
    cleaned = host.strip()
    if not cleaned or any(char.isspace() for char in cleaned) or "://" in cleaned or "/" in cleaned:
        raise DatabaseError("Enter a hostname or IP address, without a URL.")
    if cleaned.lower() in _BLOCKED_HOSTS:
        raise DatabaseError("That host is not allowed.")
    return cleaned


def postgres_url(host: str, port: int, database: str, username: str, password: str) -> str:
    return (
        f"postgresql+psycopg://{quote_plus(username)}:{quote_plus(password)}"
        f"@{host}:{port}/{quote_plus(database)}"
    )


def sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


def get_engine(url: str, dialect: str) -> Engine:
    with _engine_lock:
        engine = _engines.get(url)
        if engine is None:
            kwargs: dict = {"pool_pre_ping": True}
            if dialect == "sqlite":
                kwargs["poolclass"] = NullPool
                kwargs["connect_args"] = {"check_same_thread": False}
            else:
                kwargs["pool_size"] = 3
                kwargs["max_overflow"] = 2
            engine = create_engine(url, **kwargs)
            if dialect == "postgresql":

                @event.listens_for(engine, "connect")
                def _postgres_readonly(dbapi_conn, _record):
                    cursor = dbapi_conn.cursor()
                    cursor.execute("SET default_transaction_read_only = on")
                    cursor.execute("SET statement_timeout = '8s'")
                    cursor.close()

            else:

                @event.listens_for(engine, "connect")
                def _sqlite_readonly(dbapi_conn, _record):
                    cursor = dbapi_conn.cursor()
                    cursor.execute("PRAGMA query_only = ON")
                    cursor.close()

            _engines[url] = engine
        return engine


def drop_engine(url: str) -> None:
    with _engine_lock:
        engine = _engines.pop(url, None)
    if engine is not None:
        engine.dispose()


def _prepare(conn, dialect: str) -> None:
    if dialect == "postgresql":
        conn.exec_driver_sql("SET statement_timeout = 8000")
        conn.exec_driver_sql("SET default_transaction_read_only = on")
    else:
        conn.exec_driver_sql("PRAGMA query_only = ON")


def ping(url: str, dialect: str) -> None:
    engine = get_engine(url, dialect)
    try:
        with engine.connect() as conn:
            _prepare(conn, dialect)
            conn.exec_driver_sql("SELECT 1")
            conn.rollback()
    except Exception as exc:
        drop_engine(url)
        raise DatabaseError(public_db_error(exc)) from exc


def quote_ident(name: str) -> str:
    if not _IDENT.fullmatch(name):
        raise DatabaseError(f"Unexpected identifier: {name}")
    return f'"{name}"'


def introspect(url: str, dialect: str) -> dict:
    engine = get_engine(url, dialect)
    try:
        inspector = inspect(engine)
        table_names = inspector.get_table_names()
    except Exception as exc:
        raise DatabaseError(public_db_error(exc)) from exc

    tables = []
    try:
        with engine.connect() as conn:
            _prepare(conn, dialect)
            for name in table_names:
                columns = []
                for column in inspector.get_columns(name):
                    columns.append(
                        {
                            "name": column["name"],
                            "type": str(column["type"]),
                            "nullable": bool(column.get("nullable", True)),
                            "primary_key": False,
                        }
                    )
                pk = inspector.get_pk_constraint(name) or {}
                pk_cols = set(pk.get("constrained_columns") or [])
                for column in columns:
                    column["primary_key"] = column["name"] in pk_cols
                foreign_keys = []
                for fk in inspector.get_foreign_keys(name):
                    referred = fk.get("referred_table") or ""
                    for local, remote in zip(fk.get("constrained_columns") or [], fk.get("referred_columns") or []):
                        foreign_keys.append(
                            {"column": local, "ref_table": referred, "ref_column": remote}
                        )
                samples = []
                try:
                    result = conn.exec_driver_sql(f"SELECT * FROM {quote_ident(name)} LIMIT 3")
                    keys = list(result.keys())
                    for row in result.fetchall():
                        samples.append({key: json_safe(value) for key, value in zip(keys, row)})
                except Exception:
                    samples = []
                tables.append(
                    {
                        "name": name,
                        "columns": columns,
                        "foreign_keys": foreign_keys,
                        "sample_rows": samples,
                    }
                )
            conn.rollback()
    except DatabaseError:
        raise
    except Exception as exc:
        raise DatabaseError(public_db_error(exc)) from exc
    return {"dialect": dialect, "tables": tables}


def execute_select(url: str, dialect: str, sql: str) -> tuple[list[str], list[dict]]:
    engine = get_engine(url, dialect)
    try:
        with engine.connect() as conn:
            _prepare(conn, dialect)
            result = conn.exec_driver_sql(sql)
            columns = list(result.keys())
            rows = [
                {column: json_safe(value) for column, value in zip(columns, row)}
                for row in result.fetchall()
            ]
            conn.rollback()
    except Exception as exc:
        raise DatabaseError(public_db_error(exc)) from exc
    return columns, rows


def resolve_target(connection: SavedConnection | None, connection_id: str) -> Target:
    if connection_id == DEMO_ID:
        return Target(
            ref=DEMO_ID,
            name=DEMO_NAME,
            kind="postgres",
            dialect="postgresql",
            url=settings.demo_database_url,
            builtin=True,
        )
    if connection is None:
        raise DatabaseError("That connection was not found.")
    if connection.kind == "sqlite":
        if not connection.sqlite_path:
            raise DatabaseError("The SQLite file for this connection is missing.")
        path = Path(connection.sqlite_path)
        if not path.is_file():
            raise DatabaseError("The SQLite file for this connection is missing.")
        return Target(
            ref=str(connection.id),
            name=connection.name,
            kind="sqlite",
            dialect="sqlite",
            url=sqlite_url(path),
            builtin=False,
        )
    password = decrypt_secret(connection.password_encrypted or "")
    return Target(
        ref=str(connection.id),
        name=connection.name,
        kind="postgres",
        dialect="postgresql",
        url=postgres_url(
            connection.host or "",
            connection.port or 5432,
            connection.database or "",
            connection.username or "",
            password,
        ),
        builtin=False,
    )


def suggestions_for(schema: dict, builtin: bool) -> list[str]:
    if builtin:
        return [
            "What are the top 5 products by paid revenue?",
            "Show monthly paid revenue for 2026",
            "Which employees have the highest average order value?",
            "How many customers joined in each region?",
            "Which products have fewer than 20 units in stock?",
        ]
    tables = [table["name"] for table in schema.get("tables", [])]
    ideas = []
    for name in tables[:3]:
        ideas.append(f"How many rows are in {name}?")
    if tables:
        ideas.append(f"Show 20 rows from {tables[0]}")
    return ideas


def dataset_note(builtin: bool) -> str:
    return DEMO_NOTE if builtin else ""
