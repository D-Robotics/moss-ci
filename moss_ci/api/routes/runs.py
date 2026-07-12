import uuid
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import asyncio, json
from moss_ci.api.schemas import RunPipelineRequest, RunPipelineResponse
from moss_ci.engine.pipeline import PipelineEngine, PipelineConfig
from moss_ci.parser.yaml_parser import parse_suite_string
from moss_ci.models.result import PipelineResult, RunStatus
import yaml

router = APIRouter(prefix="/api/v1")
# SCAFFOLD ONLY: in-memory store. The RunRepository built in Task 8 (PostgreSQL)
# is NOT wired in here yet — that switchover is Task 16. Tests in Task 10/11 pass
# against this in-memory store; once Task 16 lands, replace _runs with the repo.
_runs: dict[str, PipelineResult] = {}


def _dict_to_suite(data: dict):
    yaml_str = yaml.dump(data, allow_unicode=True)
    return parse_suite_string(yaml_str)


@router.post("/pipelines/run", response_model=RunPipelineResponse)
async def run_pipeline(req: RunPipelineRequest):
    run_id = str(uuid.uuid4())[:8]
    suites = [_dict_to_suite(s) for s in req.suites]
    engine = PipelineEngine(PipelineConfig(pipeline_name=req.pipeline_name))
    result = await engine.run(suites)
    result.run_id = run_id
    _runs[run_id] = result
    return RunPipelineResponse(run_id=run_id, pipeline_name=req.pipeline_name, status=result.status.value)


@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail="Run not found")
    result = _runs[run_id]
    return result.model_dump()


@router.get("/runs/{run_id}/logs")
async def get_run_logs(run_id: str):
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail="Run not found")
    async def event_stream():
        result = _runs[run_id]
        for suite in result.suites:
            for test in suite.tests:
                yield f"data: {json.dumps({'test': test.test_name, 'status': test.status})}\n\n"
                await asyncio.sleep(0.01)
        yield f"data: {json.dumps({'status': result.status.value, 'summary': result.summary})}\n\n"
    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/runs/{run_id}/cancel")
async def cancel_run(run_id: str):
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail="Run not found")
    _runs[run_id].status = RunStatus.CANCELLED
    return {"run_id": run_id, "status": "cancelled"}


@router.get("/runs")
async def list_runs(limit: int = 20, offset: int = 0):
    all_runs = list(_runs.values())
    all_runs.sort(key=lambda r: r.created_at, reverse=True)
    page = all_runs[offset:offset + limit]
    return [r.model_dump() for r in page]


@router.get("/runs/{run_id}/diff")
async def diff_run(run_id: str):
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail="Run not found")
    current = _runs[run_id]
    all_runs = sorted([r for r in _runs.values() if r.run_id != run_id], key=lambda r: r.created_at, reverse=True)
    previous = all_runs[0] if all_runs else None
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
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail="Run not found")
    tests = []
    for suite in _runs[run_id].suites:
        for test in suite.tests:
            tests.append({"suite_name": suite.suite_name, **test.model_dump()})
    return tests


@router.get("/runs/{run_id}/tests/{test_name}")
async def get_test_detail(run_id: str, test_name: str):
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail="Run not found")
    for suite in _runs[run_id].suites:
        for test in suite.tests:
            if test.test_name == test_name:
                return {"suite_name": suite.suite_name, **test.model_dump()}
    raise HTTPException(status_code=404, detail="Test not found")


@router.get("/suites")
async def list_suites():
    suite_names = set()
    for run in _runs.values():
        for suite in run.suites:
            suite_names.add(suite.suite_name)
    return list(suite_names)


@router.get("/suites/{name}/history")
async def suite_history(name: str, limit: int = 20):
    history = []
    for run in sorted(_runs.values(), key=lambda r: r.created_at, reverse=True):
        for suite in run.suites:
            if suite.suite_name == name:
                history.append({"run_id": run.run_id, "date": run.created_at.isoformat(), "passed": suite.passed, "failed": suite.failed, "total": suite.total})
    return history[:limit]
