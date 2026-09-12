import os
from pathlib import Path
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# Base directory for the AASRA project
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "disaster.db"

# SQLite connection URL
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields an independent database session per request
    and ensures it is properly closed upon completion.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()