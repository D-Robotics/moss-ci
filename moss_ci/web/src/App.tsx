import { Routes, Route, Link } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import RunDetail from './pages/RunDetail'

export default function App() {
  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: 20 }}>
      <header style={{ borderBottom: '1px solid #e0e0e0', marginBottom: 24, paddingBottom: 12 }}>
        <h1 style={{ margin: 0 }}><Link to="/" style={{ textDecoration: 'none', color: '#333' }}>Moss CI</Link></h1>
      </header>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/runs/:runId" element={<RunDetail />} />
      </Routes>
    </div>
  )
}
