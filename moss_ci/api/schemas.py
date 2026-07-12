from pydantic import BaseModel, Field
from moss_ci.models.pipeline import SuiteConfig


class RunPipelineRequest(BaseModel):
    suites: list[dict] = Field(description="Suite configs as dicts")
    pipeline_name: str = Field(default="api-pipeline")

class RunPipelineResponse(BaseModel):
    run_id: str
    pipeline_name: str
    status: str
