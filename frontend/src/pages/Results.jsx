import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { getWorks } from '../api'

const FRAUD_TYPES = ['', 'duplicate', 'stalled', 'zero_disbursal', 'sanction_overrun', 'amount_mismatch']

export default function Results() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [filters, setFilters] = useState({
    mp: '', state: '', fraud_type: '', min_risk: 0, page: 1,
  })

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await getWorks(filters)
      setData(res)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [filters])

  useEffect(() => { fetchData() }, [fetchData])

  const totalPages = data ? Math.ceil(data.total / data.page_size) : 0

  return (
    <div className="container page">
      <div style={{ marginBottom: 32 }}>
        <h1 className="heading-lg" style={{ marginBottom: 4 }}>Flagged Works</h1>
        <p className="body-sm" style={{ color: 'var(--gray-500)' }}>
          {data ? `${data.total} results` : 'Loading...'}
        </p>
      </div>

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
        gap: 12,
        marginBottom: 24,
      }}>
        <input
          className="input"
          placeholder="Search MP name..."
          value={filters.mp}
          onChange={(e) => setFilters((f) => ({ ...f, mp: e.target.value, page: 1 }))}
        />
        <input
          className="input"
          placeholder="State..."
          value={filters.state}
          onChange={(e) => setFilters((f) => ({ ...f, state: e.target.value, page: 1 }))}
        />
        <select
          className="select"
          value={filters.fraud_type}
          onChange={(e) => setFilters((f) => ({ ...f, fraud_type: e.target.value, page: 1 }))}
        >
          {FRAUD_TYPES.map((t) => (
            <option key={t} value={t}>{t || 'All fraud types'}</option>
          ))}
        </select>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <input
            type="range"
            min="0"
            max="100"
            value={filters.min_risk}
            onChange={(e) => setFilters((f) => ({ ...f, min_risk: Number(e.target.value), page: 1 }))}
          />
          <span className="mono-sm" style={{ minWidth: 32, textAlign: 'right' }}>
            {filters.min_risk}
          </span>
        </div>
      </div>

      {error && (
        <div style={{
          padding: '12px 16px', background: '#f8d7da', color: '#842029',
          borderRadius: 'var(--radius-md)', marginBottom: 24, fontSize: '0.875rem',
        }}>
          {error}
        </div>
      )}

      {loading ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="skeleton" style={{ height: 48 }} />
          ))}
        </div>
      ) : data && (
        <>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Work ID</th>
                  <th>MP Name</th>
                  <th>State</th>
                  <th>Description</th>
                  <th>Sanction (₹)</th>
                  <th>Avg Risk / Work</th>
                  <th>Cumulative Risk Pts</th>
                  <th>Fraud Type</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {data.results.map((w) => (
                  <tr key={w.work_id}>
                    <td>
                      <span className="mono" style={{ fontSize: '0.8125rem' }}>
                        {w.work_id}
                      </span>
                    </td>
                    <td style={{ fontWeight: 500 }}>{w.mp_name}</td>
                    <td>{w.state}</td>
                    <td style={{ maxWidth: 280 }}>
                      <span style={{
                        display: '-webkit-box',
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: 'vertical',
                        overflow: 'hidden',
                      }}>
                        {w.work_desc}
                      </span>
                    </td>
                    <td className="mono" style={{ fontSize: '0.8125rem' }}>
                      {w.sanction_amount != null ? `₹${Number(w.sanction_amount).toLocaleString('en-IN')}` : '—'}
                    </td>
                    <td>
                      <span className="badge badge-warning">
                        {w.risk_score != null ? w.risk_score.toFixed(1) : '—'}
                      </span>
                    </td>
                    <td>
                      <span className="badge badge-danger">
                        {w.cumulative_risk_points != null ? Number(w.cumulative_risk_points).toLocaleString('en-IN') : '—'}
                      </span>
                    </td>
                    <td>
                      <span className="badge badge-info">
                        {w.fraud_type || '—'}
                      </span>
                    </td>
                    <td>
                      <Link to={`/works/${encodeURIComponent(w.work_id)}`}>
                        <button className="btn btn-ghost btn-sm">View</button>
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              gap: 8, marginTop: 24,
            }}>
              <button
                className="btn btn-secondary btn-sm"
                disabled={filters.page <= 1}
                onClick={() => setFilters((f) => ({ ...f, page: f.page - 1 }))}
              >
                Previous
              </button>
              <span className="mono-sm">
                Page {data.page} of {totalPages}
              </span>
              <button
                className="btn btn-secondary btn-sm"
                disabled={filters.page >= totalPages}
                onClick={() => setFilters((f) => ({ ...f, page: f.page + 1 }))}
              >
                Next
              </button>
            </div>
          )}

          <p style={{
            marginTop: 16, textAlign: 'center', fontSize: '0.8125rem',
            color: 'var(--gray-400)',
          }}>
            Possible fraud pattern — verification required by scheme authority.
          </p>
        </>
      )}
    </div>
  )
}
