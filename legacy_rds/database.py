"""
Database Connection and Session Management.
Supports both AWS RDS PostgreSQL and Local SQLite / Postgres fallback.
"""
import os
from typing import Generator
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# Load environment variables
load_dotenv()

# Fallback to local SQLite if DATABASE_URL is not set or empty
DEFAULT_DB_URL = "sqlite:///./assignment_portal.db"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DB_URL)

# Normalize old postgres:// URI scheme if passed
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Configure engine arguments based on database dialect
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
    engine = create_engine(
        DATABASE_URL,
        connect_args=connect_args,
        echo=False,
    )
else:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        echo=False,
    )

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base model class for all SQLAlchemy declarative entities."""
    pass


def get_db() -> Generator:
    """
    FastAPI dependency yielding database session per request.
    Ensures clean session closure.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
