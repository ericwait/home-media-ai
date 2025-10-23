"""Database connection and session management.

Provides convenient helpers for creating database sessions with automatic
configuration loading and lifecycle management.
"""

from contextlib import contextmanager
from typing import Optional, Generator

from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import Session, sessionmaker

from .config import Config, get_config


# Global engine instance (lazy initialization)
_engine: Optional[Engine] = None
_SessionFactory: Optional[sessionmaker] = None


def get_engine(config: Optional[Config] = None) -> Engine:
    """Get or create the global database engine.

    The engine is created once and reused for all sessions.

    Args:
        config: Optional Config instance. If None, loads from config.yaml

    Returns:
        SQLAlchemy Engine instance

    Raises:
        ValueError: If no database URI is configured

    Example:
        >>> engine = get_engine()
        >>> print(engine.url)
    """
    global _engine, _SessionFactory

    if _engine is None:
        if config is None:
            config = get_config()

        if not config.database.uri:
            raise ValueError(
                "No database URI configured. Set database.uri in config.yaml "
                "or use HOME_MEDIA_AI_URI environment variable."
            )

        _engine = create_engine(config.database.uri)
        _SessionFactory = sessionmaker(bind=_engine)

    return _engine


def get_session(config: Optional[Config] = None) -> Session:
    """Create a new database session.

    The session must be closed manually when done:
        session = get_session()
        try:
            # ... use session ...
        finally:
            session.close()

    For automatic cleanup, use session_scope() context manager instead.

    Args:
        config: Optional Config instance. If None, loads from config.yaml

    Returns:
        New SQLAlchemy Session instance

    Example:
        >>> session = get_session()
        >>> results = session.query(Media).all()
        >>> session.close()
    """
    global _SessionFactory

    if _SessionFactory is None:
        get_engine(config)

    return _SessionFactory()


@contextmanager
def session_scope(config: Optional[Config] = None) -> Generator[Session, None, None]:
    """Provide a transactional scope for database operations.

    Automatically commits on success and rolls back on exception.
    Session is always closed when exiting the context.

    Args:
        config: Optional Config instance. If None, loads from config.yaml

    Yields:
        SQLAlchemy Session instance

    Example:
        >>> with session_scope() as session:
        ...     results = session.query(Media).filter(Media.rating == 5).all()
        ...     # Session auto-commits and closes here
    """
    session = get_session(config)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_engine():
    """Reset the global engine instance.

    Useful for testing or when switching database connections.
    """
    global _engine, _SessionFactory

    if _engine:
        _engine.dispose()

    _engine = None
    _SessionFactory = None