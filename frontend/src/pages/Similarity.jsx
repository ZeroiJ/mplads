import { useState } from 'react'
import { Link } from 'react-router-dom'
import { getSimilar } from '../api'

export default function Similarity() {
  const [desc, setDesc] = useState('')
  const [k, setK] = useState(5)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleSearch = async () => {
    if (!desc.trim()) return
    setLoading(true)
    setError(null)
    try {
      const res = await getSimilar(desc, k)
      setData(res)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="container page" style={{ maxWidth: 720 }}>
      <h1 className="heading-lg" style={{ marginBottom: 4 }}>Similarity Search</h1>
      <p className="body-sm" style={{ color: 'var(--gray-500)', marginBottom: 32 }}>
        Type a work description to find similar flagged works.
      </p>

      <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
        <input
          className="input"
          placeholder="e.g. Construction of pucca house for BPL family..."
          value={desc}
          onChange={(e) => setDesc(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          style={{ flex: 1 }}
        />
        <select
          className="select"
          style={{ width: 80 }}
          value={k}
          onChange={(e) => setK(Number(e.target.value))}
        >
          {[3, 5, 10, 20].map((n) => (
            <option key={n} value={n}>Top {n}</option>
          ))}
        </select>
        <button
          className="btn btn-primary"
          disabled={loading || !desc.trim()}
          onClick={handleSearch}
        >
          {loading ? 'Searching...' : 'Search'}
        </button>
      </div>

      {error && (
        <div style={{
          padding: '12px 16px', background: '#f8d7da', color: '#842029',
          borderRadius: 'var(--radius-md)', marginBottom: 24, fontSize: '0.875rem',
        }}>
          {error}
        </div>
      )}

      {data && (
        <div>
          <p className="body-sm" style={{ color: 'var(--gray-500)', marginBottom: 16 }}>
            {data.similar.length} similar works found
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {data.similar.map((s) => (
              <Link key={s.work_id} to={`/works/${encodeURIComponent(s.work_id)}`}>
                <div className="card" style={{
                  padding: 16, display: 'flex', justifyContent: 'space-between',
                  alignItems: 'flex-start', gap: 16, transition: 'box-shadow 0.15s',
                }}>
                  <div style={{ flex: 1 }}>
                    <div className="mono" style={{ fontSize: '0.8125rem', color: 'var(--gray-400)', marginBottom: 4 }}>
                      {s.work_id}
                    </div>
                    <div className="body-sm">{s.work_desc}</div>
                  </div>
                  <div style={{ textAlign: 'right', flexShrink: 0 }}>
                    <span className="badge badge-info">
                      {(s.score * 100).toFixed(1)}% match
                    </span>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
