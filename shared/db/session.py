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

def create_db_engine(url: str, **kwargs):
    return create_async_engine(url, **kwargs)

def get_session_factory():
    return async_session_factory

async def init_db(engine_instance=None):
    from shared.db.models import Base
    if engine_instance is None:
        engine_instance = engine
    async with engine_instance.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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
