import { Link } from 'react-router-dom'
import { RunSummary } from '../api'

export default function RunList({ runs }: { runs: RunSummary[] }) {
  if (runs.length === 0) return <p>No runs yet.</p>
  return (
    <div>
      {runs.map(run => (
        <div key={run.run_id} style={{ border: '1px solid #e0e0e0', borderRadius: 4, padding: 12, marginBottom: 8 }}>
          <Link to={`/runs/${run.run_id}`}><strong>{run.run_id}</strong></Link>
          <span style={{ marginLeft: 16, color: run.status === 'success' ? 'green' : 'red' }}>{run.status}</span>
          <span style={{ marginLeft: 16, color: '#666' }}>{run.summary}</span>
        </div>
      ))}
    </div>
  )
}
