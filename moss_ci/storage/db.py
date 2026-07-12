from __future__ import annotations
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker, AsyncEngine
from moss_ci.storage.models import Base

_db_instance: Database | None = None


class Database:
    def __init__(self, url: str = ""):
        # Explicit url wins; else env var; else default file SQLite.
        self.url = url or os.environ.get("MOSS_CI_DB_URL", "") or "sqlite+aiosqlite:///moss_ci.db"
        self.engine: AsyncEngine | None = None
        self.session_factory: async_sessionmaker[AsyncSession] | None = None

    async def init(self):
        # Idempotent: safe to call from lifespan AND from request paths
        # (e.g. tests via httpx ASGITransport, which does not fire lifespan).
        if self.session_factory is not None:
            return
        self.engine = create_async_engine(self.url, echo=False)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def close(self):
        if self.engine:
            await self.engine.dispose()

    def get_session(self) -> AsyncSession:
        if self.session_factory is None:
            raise RuntimeError("Database not initialized. Call db.init() first.")
        return self.session_factory()


def get_db(url: str = "") -> Database:
    global _db_instance
    if _db_instance is None:
        _db_instance = Database(url)
    return _db_instance
