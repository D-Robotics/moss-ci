const BASE = '/api/v1'

export interface RunSummary {
  run_id: string; pipeline_name: string; status: string;
  summary: string; created_at: string; total_duration: number;
  suites: SuiteSummary[];
}
export interface SuiteSummary {
  suite_name: string; total: number; passed: number; failed: number; error: number;
  tests: TestSummary[];
}
export interface TestSummary {
  test_name: string; status: string; duration: number; moss_output: string;
  evals: { type: string; passed: boolean; score?: number }[];
}

export async function fetchRuns(limit = 20): Promise<RunSummary[]> {
  const r = await fetch(`${BASE}/runs?limit=${limit}`)
  return r.json()
}
export async function fetchRun(runId: string): Promise<RunSummary> {
  const r = await fetch(`${BASE}/runs/${runId}`)
  return r.json()
}
export async function fetchDiff(runId: string): Promise<any> {
  const r = await fetch(`${BASE}/runs/${runId}/diff`)
  return r.json()
}
export async function runPipeline(suites: any[]): Promise<{ run_id: string }> {
  const r = await fetch(`${BASE}/pipelines/run`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ suites }),
  })
  return r.json()
}
