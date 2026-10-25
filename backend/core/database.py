"""SQLAlchemy engine + session for Trạm Trading SQLite."""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DEFAULT_DB = Path(os.getenv("TRADING_DB_PATH", "data/dev_trading.db"))


class Base(DeclarativeBase):
    pass


def _sqlite_url(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path.resolve()}"


_engine = None
_SessionLocal: sessionmaker[Session] | None = None
_db_path: Path | None = None


def reset_engine() -> None:
    global _engine, _SessionLocal, _db_path
    _engine = None
    _SessionLocal = None
    _db_path = None


def get_engine(db_path: Path | None = None):
    global _engine, _SessionLocal, _db_path
    path = db_path or DEFAULT_DB
    if _engine is None or _db_path != path:
        _db_path = path
        _engine = create_engine(
            _sqlite_url(path),
            connect_args={"check_same_thread": False},
            future=True,
        )
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    return _engine


def get_session_factory(db_path: Path | None = None) -> sessionmaker[Session]:
    get_engine(db_path)
    assert _SessionLocal is not None
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    factory = get_session_factory()
    db = factory()
    try:
        yield db
    finally:
        db.close()


def init_db(db_path: Path | None = None) -> None:
    from backend.modules.trading import models  # noqa: F401

    engine = get_engine(db_path)
    Base.metadata.create_all(bind=engine)
