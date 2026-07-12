import pytest
from httpx import ASGITransport, AsyncClient
from moss_ci.api.server import create_app


@pytest.fixture
async def client():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestPipelineRun:
    @pytest.mark.asyncio
    async def test_run_pipeline(self, client):
        resp = await client.post("/api/v1/pipelines/run", json={
            "suites": [{
                "name": "test-suite", "version": "1.0",
                "tests": [{"name": "t1", "moss": {"prompt": "hello"}, "eval": [{"type": "contains", "value": "world"}]}]
            }]
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "run_id" in data
        assert data["status"] in ("running", "success", "failed")

    @pytest.mark.asyncio
    async def test_get_run_status(self, client):
        # First create a run
        run_resp = await client.post("/api/v1/pipelines/run", json={
            "suites": [{"name": "s1", "version": "1.0",
                        "tests": [{"name": "t1", "moss": {"prompt": "hi"}, "eval": [{"type": "contains", "value": "hi"}]}]}]
        })
        run_id = run_resp.json()["run_id"]
        resp = await client.get(f"/api/v1/runs/{run_id}")
        assert resp.status_code == 200
        assert resp.json()["run_id"] == run_id
