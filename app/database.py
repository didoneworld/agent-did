from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.config import settings


Base = declarative_base()
engine = None
SessionLocal = None


def init_database(database_url: str | None = None):
    global engine, SessionLocal
    resolved_url = database_url or settings.database_url
    if resolved_url.startswith("sqlite:///"):
        db_file = Path(resolved_url.replace("sqlite:///", "", 1))
        db_file.parent.mkdir(parents=True, exist_ok=True)
        connect_args = {"check_same_thread": False}
    else:
        connect_args = {}
    engine = create_engine(resolved_url, future=True, connect_args=connect_args)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return engine


init_database()


def get_db() -> Generator[Session, None, None]:
    if SessionLocal is None:
        init_database()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
