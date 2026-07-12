import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { RunSummary } from '../api'

export default function TrendChart({ runs }: { runs: RunSummary[] }) {
  const data = [...runs].reverse().slice(-10).map(run => {
    const total = run.suites.reduce((s, suite) => s + suite.passed, 0)
    const failed = run.suites.reduce((s, suite) => s + suite.failed + suite.error, 0)
    return { name: run.run_id, passed: total, failed }
  })
  if (data.length === 0) return <p>No data for chart.</p>
  return (
    <div style={{ marginBottom: 24 }}>
      <h3>Pass/Fail Trend</h3>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" />
          <YAxis />
          <Tooltip />
          <Bar dataKey="passed" fill="#4caf50" stackId="a" />
          <Bar dataKey="failed" fill="#f44336" stackId="a" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
