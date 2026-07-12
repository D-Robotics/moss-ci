import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchRuns, RunSummary } from '../api'
import TrendChart from '../components/TrendChart'

export default function Dashboard() {
  const [runs, setRuns] = useState<RunSummary[]>([])
  useEffect(() => { fetchRuns().then(setRuns) }, [])

  return (
    <div>
      <h2>Dashboard</h2>
      <TrendChart runs={runs} />
      <h3>Recent Runs</h3>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ borderBottom: '2px solid #e0e0e0' }}>
            <th style={{ textAlign: 'left', padding: 8 }}>Run ID</th>
            <th style={{ textAlign: 'left', padding: 8 }}>Pipeline</th>
            <th style={{ textAlign: 'left', padding: 8 }}>Status</th>
            <th style={{ textAlign: 'left', padding: 8 }}>Summary</th>
            <th style={{ textAlign: 'left', padding: 8 }}>Time</th>
          </tr>
        </thead>
        <tbody>
          {runs.map(run => (
            <tr key={run.run_id} style={{ borderBottom: '1px solid #f0f0f0' }}>
              <td style={{ padding: 8 }}><Link to={`/runs/${run.run_id}`}>{run.run_id}</Link></td>
              <td style={{ padding: 8 }}>{run.pipeline_name}</td>
              <td style={{ padding: 8, color: run.status === 'success' ? 'green' : run.status === 'failed' ? 'red' : 'orange' }}>{run.status}</td>
              <td style={{ padding: 8 }}>{run.summary}</td>
              <td style={{ padding: 8 }}>{new Date(run.created_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
