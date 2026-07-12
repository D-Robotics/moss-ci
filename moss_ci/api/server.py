from fastapi import FastAPI
from contextlib import asynccontextmanager
from moss_ci.api.routes.runs import router as runs_router
from moss_ci.storage.db import get_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = get_db()
    await db.init()
    yield
    await db.close()


def create_app() -> FastAPI:
    app = FastAPI(title="Moss CI", version="0.1.0", lifespan=lifespan)
    app.include_router(runs_router)

    @app.get("/health")
    async def health():
        return {"status": "ok", "version": "0.1.0"}

    return app


app = create_app()
