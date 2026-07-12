import pytest
from httpx import ASGITransport, AsyncClient
from moss_ci.api.server import create_app


@pytest.fixture
async def client():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestAdvancedEndpoints:
    @pytest.mark.asyncio
    async def test_list_runs(self, client):
        resp = await client.get("/api/v1/runs")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_diff(self, client):
        # Create two runs
        r1 = await client.post("/api/v1/pipelines/run", json={
            "suites": [{"name": "s1", "version": "1.0",
                        "tests": [{"name": "t1", "moss": {"prompt": "hi"}, "eval": [{"type": "contains", "value": "hi"}]}]}]
        })
        r2 = await client.post("/api/v1/pipelines/run", json={
            "suites": [{"name": "s1", "version": "1.0",
                        "tests": [{"name": "t1", "moss": {"prompt": "hi"}, "eval": [{"type": "contains", "value": "hi"}]}]}]
        })
        resp = await client.get(f"/api/v1/runs/{r2.json()['run_id']}/diff")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_list_tests(self, client):
        r = await client.post("/api/v1/pipelines/run", json={
            "suites": [{"name": "s1", "version": "1.0",
                        "tests": [{"name": "t1", "moss": {"prompt": "hi"}, "eval": [{"type": "contains", "value": "hi"}]}]}]
        })
        run_id = r.json()["run_id"]
        resp = await client.get(f"/api/v1/runs/{run_id}/tests")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
