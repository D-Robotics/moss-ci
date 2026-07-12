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
