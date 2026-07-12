import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { fetchRun, fetchDiff, RunSummary } from '../api'

export default function RunDetail() {
  const { runId } = useParams<{ runId: string }>()
  const [run, setRun] = useState<RunSummary | null>(null)
  const [diff, setDiff] = useState<any>(null)

  useEffect(() => {
    if (runId) { fetchRun(runId).then(setRun); fetchDiff(runId).then(setDiff) }
  }, [runId])

  if (!run) return <div>Loading...</div>

  return (
    <div>
      <Link to="/">← Back</Link>
      <h2>Run {run.run_id}</h2>
      <p>Status: <strong style={{ color: run.status === 'success' ? 'green' : 'red' }}>{run.status}</strong></p>
      <p>{run.summary}</p>
      {diff && (diff.new_failures?.length > 0 || diff.fixed?.length > 0) && (
        <div style={{ background: '#fff3cd', padding: 12, borderRadius: 4, marginBottom: 16 }}>
          <h4>Regression Analysis</h4>
          {diff.new_failures?.length > 0 && <p style={{ color: 'red' }}>⚠ {diff.new_failures.length} new failure(s)</p>}
          {diff.fixed?.length > 0 && <p style={{ color: 'green' }}>✓ {diff.fixed.length} fixed</p>}
        </div>
      )}
      <h3>Suites</h3>
      {run.suites.map(suite => (
        <div key={suite.suite_name} style={{ marginBottom: 16 }}>
          <h4>{suite.suite_name} ({suite.passed}/{suite.total} passed)</h4>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #e0e0e0' }}>
                <th style={{ textAlign: 'left', padding: 8 }}>Test</th>
                <th style={{ textAlign: 'left', padding: 8 }}>Status</th>
                <th style={{ textAlign: 'left', padding: 8 }}>Duration</th>
                <th style={{ textAlign: 'left', padding: 8 }}>Evaluations</th>
              </tr>
            </thead>
            <tbody>
              {suite.tests.map(test => (
                <tr key={test.test_name} style={{ borderBottom: '1px solid #f0f0f0' }}>
                  <td style={{ padding: 8 }}>{test.test_name}</td>
                  <td style={{ padding: 8, color: test.status === 'pass' ? 'green' : 'red' }}>{test.status}</td>
                  <td style={{ padding: 8 }}>{test.duration.toFixed(1)}s</td>
                  <td style={{ padding: 8 }}>
                    {test.evals.map((ev, i) => (
                      <span key={i} style={{ marginRight: 8, color: ev.passed ? 'green' : 'red' }}>
                        {ev.type}: {ev.passed ? '✓' : '✗'}{ev.score != null ? ` (${ev.score})` : ''}
                      </span>
                    ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  )
}
