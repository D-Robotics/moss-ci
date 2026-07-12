import uuid
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import asyncio, json
from moss_ci.api.schemas import RunPipelineRequest, RunPipelineResponse
from moss_ci.engine.pipeline import PipelineEngine, PipelineConfig
from moss_ci.runner.base import MossRunner
from moss_ci.parser.yaml_parser import parse_suite_string
from moss_ci.models.result import PipelineResult, RunStatus
from moss_ci.storage.db import get_db
from moss_ci.storage.repository import RunRepository
import yaml

router = APIRouter(prefix="/api/v1")


async def _repo() -> RunRepository:
    # Ensure the DB is initialized even when the lifespan didn't fire
    # (e.g. httpx ASGITransport in tests). init() is idempotent.
    db = get_db()
    await db.init()
    return RunRepository(db)


def _dict_to_suite(data: dict):
    yaml_str = yaml.dump(data, allow_unicode=True)
    return parse_suite_string(yaml_str)


@router.post("/pipelines/run", response_model=RunPipelineResponse)
async def run_pipeline(req: RunPipelineRequest):
    run_id = str(uuid.uuid4())[:8]
    suites = [_dict_to_suite(s) for s in req.suites]
    # Switchover: pass a real MossRunner (auto-detects backend from env).
    # Pass runner=None to keep scaffold behavior during local dev if desired.
    runner = MossRunner()
    engine = PipelineEngine(PipelineConfig(pipeline_name=req.pipeline_name), runner=runner)
    result = await engine.run(suites)
    result.run_id = run_id
    repo = await _repo()
    await repo.save(result)
    return RunPipelineResponse(run_id=run_id, pipeline_name=req.pipeline_name, status=result.status.value)


@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    repo = await _repo()
    result = await repo.get(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return result.model_dump()


@router.get("/runs/{run_id}/logs")
async def get_run_logs(run_id: str):
    repo = await _repo()
    result = await repo.get(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Run not found")
    async def event_stream():
        for suite in result.suites:
            for test in suite.tests:
                yield f"data: {json.dumps({'test': test.test_name, 'status': test.status})}\n\n"
                await asyncio.sleep(0.01)
        yield f"data: {json.dumps({'status': result.status.value, 'summary': result.summary})}\n\n"
    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/runs/{run_id}/cancel")
async def cancel_run(run_id: str):
    repo = await _repo()
    result = await repo.get(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Run not found")
    result.status = RunStatus.CANCELLED
    await repo.save(result)
    return {"run_id": run_id, "status": "cancelled"}


@router.get("/runs")
async def list_runs(limit: int = 20, offset: int = 0):
    repo = await _repo()
    results = await repo.list(limit=limit, offset=offset)
    return [r.model_dump() for r in results]


@router.get("/runs/{run_id}/diff")
async def diff_run(run_id: str):
    repo = await _repo()
    current = await repo.get(run_id)
    if current is None:
        raise HTTPException(status_code=404, detail="Run not found")
    all_runs = await repo.list(limit=1000)
    previous_runs = sorted([r for r in all_runs if r.run_id != run_id], key=lambda r: r.created_at, reverse=True)
    previous = previous_runs[0] if previous_runs else None
    diff = {"new_failures": [], "fixed": [], "improved": [], "degraded": []}
    if previous:
        for cur_suite in current.suites:
            prev_suite = next((s for s in previous.suites if s.suite_name == cur_suite.suite_name), None)
            if prev_suite:
                for cur_test in cur_suite.tests:
                    prev_test = next((t for t in prev_suite.tests if t.test_name == cur_test.test_name), None)
                    if prev_test:
                        if prev_test.status == "pass" and cur_test.status == "fail":
                            diff["new_failures"].append({"test_name": cur_test.test_name, "previous_status": prev_test.status, "current_status": cur_test.status})
                        elif prev_test.status == "fail" and cur_test.status == "pass":
                            diff["fixed"].append({"test_name": cur_test.test_name})
    return diff


@router.get("/runs/{run_id}/tests")
async def list_tests(run_id: str):
    repo = await _repo()
    result = await repo.get(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Run not found")
    tests = []
    for suite in result.suites:
        for test in suite.tests:
            tests.append({"suite_name": suite.suite_name, **test.model_dump()})
    return tests


@router.get("/runs/{run_id}/tests/{test_name}")
async def get_test_detail(run_id: str, test_name: str):
    repo = await _repo()
    result = await repo.get(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Run not found")
    for suite in result.suites:
        for test in suite.tests:
            if test.test_name == test_name:
                return {"suite_name": suite.suite_name, **test.model_dump()}
    raise HTTPException(status_code=404, detail="Test not found")


@router.get("/suites")
async def list_suites():
    repo = await _repo()
    suite_names = set()
    for run in await repo.list(limit=1000):
        for suite in run.suites:
            suite_names.add(suite.suite_name)
    return list(suite_names)


@router.get("/suites/{name}/history")
async def suite_history(name: str, limit: int = 20):
    repo = await _repo()
    history = []
    for run in sorted(await repo.list(limit=1000), key=lambda r: r.created_at, reverse=True):
        for suite in run.suites:
            if suite.suite_name == name:
                history.append({"run_id": run.run_id, "date": run.created_at.isoformat(), "passed": suite.passed, "failed": suite.failed, "total": suite.total})
    return history[:limit]
