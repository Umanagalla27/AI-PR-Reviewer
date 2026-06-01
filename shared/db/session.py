from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from shared.config.settings import settings
import contextlib

# Create async engine with connection pooling config
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=5,
    max_overflow=15, # pool_size + max_overflow = 20 (max_size=20)
    pool_pre_ping=True,
    echo=False
)

# Async session factory
async_session_factory = async_sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False,
    autoflush=False,
    autocommit=False
)

@contextlib.asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for database sessions.
    Usage:
        async with get_db_session() as session:
            await session.execute(...)
    """
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
