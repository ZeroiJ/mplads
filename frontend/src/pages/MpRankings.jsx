import { useState, useEffect } from 'react'
import { getOffenders } from '../api'

export default function MpRankings() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [top, setTop] = useState(20)

  useEffect(() => {
    setLoading(true)
    getOffenders(top)
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [top])

  return (
    <div className="container page">
      <div style={{ marginBottom: 32, display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', flexWrap: 'wrap', gap: 16 }}>
        <div>
          <h1 className="heading-lg" style={{ marginBottom: 4 }}>MP Leaderboard</h1>
          <p className="body-sm" style={{ color: 'var(--gray-500)' }}>
            Ranked by cumulative risk points
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span className="body-sm" style={{ color: 'var(--gray-500)' }}>Top</span>
          <select
            className="select"
            style={{ width: 80 }}
            value={top}
            onChange={(e) => setTop(Number(e.target.value))}
          >
            {[10, 20, 50, 100].map((n) => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
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
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="skeleton" style={{ height: 56 }} />
          ))}
        </div>
      ) : data && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th style={{ width: 48 }}>#</th>
                <th>MP Name</th>
                <th>Cumulative Risk Points</th>
                <th>Avg Risk / Work</th>
                <th>Risk Rank</th>
              </tr>
            </thead>
            <tbody>
              {data.mps.map((mp, i) => (
                <tr key={mp.mp_name + i}>
                  <td>
                    <span className="mono-sm">{i + 1}</span>
                  </td>
                  <td style={{ fontWeight: 500 }}>{mp.mp_name}</td>
                  <td>
                    <span className="badge badge-danger" style={{ fontSize: '0.875rem' }}>
                      {mp.cumulative_risk_points != null
                        ? Number(mp.cumulative_risk_points).toLocaleString('en-IN')
                        : '—'}
                    </span>
                  </td>
                  <td>
                    <span className="badge badge-warning">
                      {mp.avg_risk_per_work != null ? mp.avg_risk_per_work.toFixed(1) : '—'}
                    </span>
                  </td>
                  <td>
                    <span className="mono" style={{ fontSize: '0.8125rem', color: 'var(--gray-500)' }}>
                      {mp.risk_rank != null ? `#${mp.risk_rank}` : '—'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p style={{
        marginTop: 24, textAlign: 'center', fontSize: '0.8125rem',
        color: 'var(--gray-400)',
      }}>
        Possible fraud pattern — verification required by scheme authority.
      </p>
    </div>
  )
}
