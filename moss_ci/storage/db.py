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
            # create_all does NOT add columns to tables that already exist, so
            # an older moss_ci.db is missing columns introduced later. SQLite
            # supports ADD COLUMN; ALTER is a no-op if the column is present.
            await self._migrate(conn)

    async def _migrate(self, conn):
        # Lightweight additive migrations only (new columns). Inspect the live
        # schema and add what's missing. Keeps a local dev DB usable without a
        # full alembic upgrade for these small, backward-compatible additions.
        from sqlalchemy import text, inspect
        def _sync(c):
            insp = inspect(c)
            cols = {c["name"] for c in insp.get_columns("test_results")} if insp.has_table("test_results") else set()
            if "test_results" in insp.get_table_names() and "flake_runs" not in cols:
                c.execute(text("ALTER TABLE test_results ADD COLUMN flake_runs JSON"))
        await conn.run_sync(_sync)

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
