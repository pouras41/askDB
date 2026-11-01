import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.crypto import decrypt_secret, encrypt_secret
from app.db import get_db
from app.deps import get_current_user
from app.models import SavedConnection, User
from app.schemas import ConnectionPublic, PostgresConnectionRequest, SchemaResponse
from app.services.database import (
    DEMO_ID,
    DEMO_NAME,
    DatabaseError,
    dataset_note,
    drop_engine,
    introspect,
    ping,
    postgres_url,
    resolve_target,
    sqlite_url,
    suggestions_for,
    validate_host,
)

router = APIRouter(prefix="/api/connections", tags=["connections"])


def _owned(db: Session, user: User, connection_id: str) -> SavedConnection:
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
    return connection


def _public(connection: SavedConnection) -> ConnectionPublic:
    if connection.kind == "sqlite":
        detail = "Uploaded SQLite file"
    else:
        detail = f"{connection.host}:{connection.port}/{connection.database}"
    return ConnectionPublic(
        id=str(connection.id),
        name=connection.name,
        kind=connection.kind,
        detail=detail,
        builtin=False,
    )


@router.get("", response_model=list[ConnectionPublic])
def list_connections(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ConnectionPublic]:
    rows = db.scalars(
        select(SavedConnection)
        .where(SavedConnection.user_id == user.id)
        .order_by(SavedConnection.created_at.desc())
    ).all()
    demo = ConnectionPublic(
        id=DEMO_ID,
        name=DEMO_NAME,
        kind="postgres",
        detail="Built-in retail database",
        builtin=True,
    )
    return [demo, *(_public(row) for row in rows)]


@router.post("", response_model=ConnectionPublic, status_code=201)
def create_postgres_connection(
    payload: PostgresConnectionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConnectionPublic:
    try:
        host = validate_host(payload.host)
    except DatabaseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    url = postgres_url(host, payload.port, payload.database.strip(), payload.username, payload.password)
    try:
        ping(url, "postgresql")
    except DatabaseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    connection = SavedConnection(
        user_id=user.id,
        name=payload.name.strip(),
        kind="postgres",
        host=host,
        port=payload.port,
        database=payload.database.strip(),
        username=payload.username,
        password_encrypted=encrypt_secret(payload.password),
    )
    db.add(connection)
    db.commit()
    db.refresh(connection)
    return _public(connection)


@router.post("/sqlite", response_model=ConnectionPublic, status_code=201)
async def upload_sqlite(
    file: UploadFile = File(...),
    name: str | None = Form(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConnectionPublic:
    data = await file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="SQLite files must be 20 MB or smaller.")
    if not data.startswith(b"SQLite format 3\x00"):
        raise HTTPException(status_code=400, detail="That file is not a SQLite database.")
    folder = (Path(settings.upload_dir) / str(user.id)).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    path = (folder / f"{uuid.uuid4().hex}.db").resolve()
    if path.parent != folder:
        raise HTTPException(status_code=400, detail="Could not store that file.")
    path.write_bytes(data)
    label = (name or file.filename or "SQLite upload").strip()
    label = Path(label).stem[:120] or "SQLite upload"
    try:
        ping(sqlite_url(path), "sqlite")
    except DatabaseError as exc:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    connection = SavedConnection(
        user_id=user.id,
        name=label,
        kind="sqlite",
        sqlite_path=str(path),
    )
    db.add(connection)
    db.commit()
    db.refresh(connection)
    return _public(connection)


@router.delete("/{connection_id}", status_code=204)
def delete_connection(
    connection_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    if connection_id == DEMO_ID:
        raise HTTPException(status_code=400, detail="The built-in demo database stays available.")
    connection = _owned(db, user, connection_id)
    if connection.kind == "sqlite" and connection.sqlite_path:
        drop_engine(sqlite_url(Path(connection.sqlite_path)))
        Path(connection.sqlite_path).unlink(missing_ok=True)
    elif connection.password_encrypted and connection.host and connection.database and connection.username:
        try:
            password = decrypt_secret(connection.password_encrypted)
            drop_engine(
                postgres_url(connection.host, connection.port or 5432, connection.database, connection.username, password)
            )
        except ValueError:
            pass
    db.delete(connection)
    db.commit()


@router.get("/{connection_id}/schema", response_model=SchemaResponse)
def connection_schema(
    connection_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SchemaResponse:
    if connection_id == DEMO_ID:
        target = resolve_target(None, DEMO_ID)
    else:
        connection = _owned(db, user, connection_id)
        try:
            target = resolve_target(connection, connection_id)
        except DatabaseError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        schema = introspect(target.url, target.dialect)
    except DatabaseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SchemaResponse(
        dialect=target.dialect,
        name=target.name,
        tables=schema["tables"],
        suggestions=suggestions_for(schema, target.builtin),
        note=dataset_note(target.builtin) or None,
    )
