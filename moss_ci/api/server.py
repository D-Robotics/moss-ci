from fastapi import FastAPI
from moss_ci.api.routes.runs import router as runs_router


def create_app() -> FastAPI:
    app = FastAPI(title="Moss CI", version="0.1.0")
    app.include_router(runs_router)

    @app.get("/health")
    async def health():
        return {"status": "ok", "version": "0.1.0"}

    return app


app = create_app()
