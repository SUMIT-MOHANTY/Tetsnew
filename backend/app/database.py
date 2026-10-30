"""
DERTOUR Database Module
SQLAlchemy 2.0 async engine + session factory with SQLite/PostgreSQL dual-mode support
"""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
    AsyncEngine,
)
from sqlalchemy.pool import NullPool

from app.core.config_loader import get_settings

settings = get_settings()

# Get the effective database URL
database_url = settings.get_database_url()

# Create async engine with appropriate configuration for SQLite or PostgreSQL
if settings.is_sqlite():
    # SQLite async configuration
    # NullPool is recommended for SQLite to avoid connection pooling issues
    engine: AsyncEngine = create_async_engine(
        database_url,
        echo=settings.DATABASE_ECHO,
        poolclass=NullPool,
        connect_args={"check_same_thread": False},
    )
else:
    # PostgreSQL async configuration with connection pooling
    engine: AsyncEngine = create_async_engine(
        database_url,
        echo=settings.DATABASE_ECHO,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        pool_pre_ping=True,  # Verify connections before using from pool
    )

# Create async session factory
# expire_on_commit=False prevents attributes from being expired after commit
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for FastAPI to get a database session.
    
    Usage:
        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db_session)):
            ...
    
    Yields:
        AsyncSession: SQLAlchemy async session
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_database_connection() -> bool:
    """
    Check if the database connection is healthy.
    
    Returns:
        bool: True if connection is successful, False otherwise
    """
    from sqlalchemy import text
    
    try:
        async with AsyncSessionLocal() as session:
            # Execute a simple query to verify connection
            result = await session.execute(text("SELECT 1"))
            await result.scalar()
            return True
    except Exception:
        return False


async def init_db() -> None:
    """
    Initialize the database by creating all tables.
    This should be called on application startup.
    
    Note: In production, use Alembic migrations instead.
    """
    from app.models.base import Base
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db_connection() -> None:
    """
    Close the database connection pool.
    This should be called on application shutdown.
    """
    await engine.dispose()


# Export commonly used items
__all__ = [
    "engine",
    "AsyncSessionLocal",
    "get_db_session",
    "check_database_connection",
    "init_db",
    "close_db_connection",
]
