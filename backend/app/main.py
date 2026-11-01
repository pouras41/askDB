import logging
import time
from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.db import Base, engine
from app.routers import auth, connections, query

logger = logging.getLogger("askdb")


def wait_for_database() -> None:
    url = settings.database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    deadline = time.time() + 60
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with psycopg.connect(url, connect_timeout=3) as conn:
                conn.execute("SELECT 1")
            return
        except Exception as exc:
            last_error = exc
            logger.info("Waiting for the application database.")
            time.sleep(2)
    raise RuntimeError(f"Application database is not ready: {last_error}")


@asynccontextmanager
async def lifespan(_: FastAPI):
    logging.basicConfig(level=logging.INFO)
    wait_for_database()
    Base.metadata.create_all(bind=engine)
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE query_history ADD COLUMN IF NOT EXISTS summary_json TEXT"))
            conn.commit()
    except Exception as exc:
        logger.warning("Could not verify summary_json column: %s", exc)
    yield
    engine.dispose()


app = FastAPI(
    title="AskDB",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(connections.router)
app.include_router(query.router)


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "gemini_configured": bool(settings.gemini_api_key.strip()),
        "model": settings.gemini_model,
    }
