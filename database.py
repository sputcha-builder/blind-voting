"""
Database connection management for PostgreSQL.
Handles engine creation, session management, and table initialization.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from contextlib import contextmanager
from models import Base

# Get database URL from environment variable
# For local testing: postgresql://user:password@localhost/dbname
# For Render: provided by DATABASE_URL environment variable
DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL environment variable is not set. "
        "Please set it to your PostgreSQL connection string."
    )

# Create SQLAlchemy engine
# pool_pre_ping=True ensures connections are alive before using them
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,  # Recycle connections after 1 hour
    echo=False  # Set to True for SQL query logging (debugging)
)

# Create session factory
# scoped_session ensures thread-safety for Flask
SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))


def init_db():
    """
    Initialize the database by creating all tables.
    Safe to call multiple times - only creates tables that don't exist.
    """
    try:
        Base.metadata.create_all(bind=engine)
        print("Database tables initialized successfully")
    except Exception as e:
        print(f"Error initializing database: {e}")
        raise


def get_session():
    """
    Get a database session.
    Use this in a context manager for automatic cleanup:

    with get_session() as session:
        # do database operations
        session.commit()
    """
    return SessionLocal()


@contextmanager
def db_session():
    """
    Context manager for database sessions.
    Automatically commits on success and rolls back on error.

    Usage:
        with db_session() as session:
            role = session.query(Role).first()
            # operations...
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def close_db():
    """
    Close all database connections.
    Call this when shutting down the application.
    """
    SessionLocal.remove()
    engine.dispose()


# Test database connection on import
try:
    # Try to connect to verify DATABASE_URL is valid
    with engine.connect() as conn:
        print(f"Successfully connected to database: {DATABASE_URL.split('@')[-1]}")  # Don't log credentials
except Exception as e:
    print(f"Failed to connect to database: {e}")
    print(f"DATABASE_URL format: postgresql://user:password@host:port/database")
    raise
