from __future__ import annotations

from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from app.core.config import get_settings


def _get_sqlite_url() -> str:
    settings = get_settings()
    # session.py -> db -> app -> backend -> python -> repo root
    db_path = Path(__file__).resolve().parents[4] / settings.sqlite_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path}"


engine = create_engine(_get_sqlite_url(), echo=False, connect_args={"check_same_thread": False})


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    return Session(engine)

