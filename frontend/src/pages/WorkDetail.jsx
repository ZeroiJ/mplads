import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import { getWorkDetail } from '../api'

function parseEvidence(md) {
  if (!md) return {}
  const sections = {}
  const lines = md.split('\n')
  let currentKey = null
  let currentLines = []

  const flush = () => {
    if (currentKey) {
      sections[currentKey] = currentLines.join('\n').trim()
    }
    currentLines = []
  }

  for (const line of lines) {
    const h2 = line.match(/^## (.+)/)
    if (h2) {
      flush()
      const title = h2[1].toLowerCase()
      if (title.includes('raw')) currentKey = 'sources'
      else if (title.includes('legal')) currentKey = 'legal'
      else if (title.includes('legitimate') || title.includes('explanation')) currentKey = 'explanations'
      else if (title.includes('verification') || title.includes('checklist')) currentKey = 'checklist'
      else if (title.includes('fraud') || title.includes('classification')) currentKey = 'classification'
      else if (title.includes('flag') || title.includes('reason')) currentKey = 'reasoning'
      else currentKey = title
    } else if (line.match(/^# Work /)) {
      flush()
      currentKey = 'header'
    } else {
      currentLines.push(line)
    }
  }
  flush()
  return sections
}

function extractRawSources(md) {
  if (!md) return []
  const sources = []
  const regex = /## Raw (\w+) row\n\n(.+?)(?=\n## |\n---|\n_Auto-generated|$)/gs
  let match
  while ((match = regex.exec(md)) !== null) {
    sources.push({ name: match[1], content: match[2].trim() })
  }
  return sources
}

export default function WorkDetail() {
  const { id } = useParams()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [verdict, setVerdict] = useState('pending')

  useEffect(() => {
    setLoading(true)
    getWorkDetail(id)
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) {
    return (
      <div className="container page">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="skeleton" style={{ height: 32, width: 200 }} />
          <div className="skeleton" style={{ height: 120 }} />
          <div className="skeleton" style={{ height: 200 }} />
          <div className="skeleton" style={{ height: 200 }} />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="container page">
        <div style={{
          padding: '16px 20px', background: '#f8d7da', color: '#842029',
          borderRadius: 'var(--radius-md)', fontSize: '0.875rem',
        }}>
          {error}
        </div>
        <Link to="/results" style={{ marginTop: 16, display: 'inline-block' }}>
          <button className="btn btn-secondary">Back to Results</button>
        </Link>
      </div>
    )
  }

  if (!data) return null

  const evidence = parseEvidence(data.evidence)
  const rawSources = extractRawSources(data.evidence)

  const summaryFields = [
    { label: 'MP Name', value: data.mp_name },
    { label: 'State', value: data.state },
    { label: 'Constituency', value: data.constituency },
    { label: 'Work Category', value: data.work_category },
    { label: 'Work Status', value: data.work_status },
  ].filter((f) => f.value)

  const amountFields = [
    { label: 'Recommended', value: data.recommended_amount, prefix: '₹' },
    { label: 'Sanctioned', value: data.sanction_amount, prefix: '₹' },
    { label: 'Disbursed', value: data.amount_disbursed, prefix: '₹' },
  ].filter((f) => f.value != null)

  return (
    <div className="container page">
      <Link to="/results" style={{ marginBottom: 24, display: 'inline-block' }}>
        <button className="btn btn-ghost btn-sm">&larr; Back to Results</button>
      </Link>

      {/* ── SECTION 1: Work Summary ── */}
      <div style={{ marginBottom: 40 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
          <h1 className="heading-lg">Work Detail</h1>
          <span className="mono" style={{ color: 'var(--gray-400)', fontSize: '0.875rem' }}>
            {data.work_id}
          </span>
        </div>
        <p className="body" style={{ color: 'var(--gray-500)', marginBottom: 4 }}>
          Possible fraud pattern — verification required by scheme authority.
        </p>
      </div>

      {/* Risk + classification bar */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
        gap: 12,
        marginBottom: 32,
      }}>
        <div className="card" style={{ padding: 16, borderLeft: '3px solid var(--black)' }}>
          <div className="mono-sm" style={{ color: 'var(--gray-400)', marginBottom: 4 }}>Avg Risk / Work</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 600 }}>
            {data.risk_score != null ? Number(data.risk_score).toFixed(1) : '—'}
          </div>
        </div>
        <div className="card" style={{ padding: 16, borderLeft: '3px solid var(--black)' }}>
          <div className="mono-sm" style={{ color: 'var(--gray-400)', marginBottom: 4 }}>Cumulative Risk Pts</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 600 }}>
            {data.cumulative_risk_points != null ? Number(data.cumulative_risk_points).toLocaleString('en-IN') : '—'}
          </div>
        </div>
        <div className="card" style={{ padding: 16, borderLeft: '3px solid var(--black)' }}>
          <div className="mono-sm" style={{ color: 'var(--gray-400)', marginBottom: 4 }}>Fraud Type</div>
          <div><span className="badge badge-info">{data.fraud_type || 'none'}</span></div>
        </div>
      </div>

      {/* Work info grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
        gap: 12,
        marginBottom: 12,
      }}>
        {summaryFields.map((f) => (
          <div key={f.label} className="card" style={{ padding: 14 }}>
            <div className="mono-sm" style={{ color: 'var(--gray-400)', marginBottom: 2 }}>{f.label}</div>
            <div className="body-sm">{f.value}</div>
          </div>
        ))}
      </div>
      {data.work_desc && (
        <div className="card" style={{ padding: 14, marginBottom: 32 }}>
          <div className="mono-sm" style={{ color: 'var(--gray-400)', marginBottom: 2 }}>Description</div>
          <div className="body-sm">{data.work_desc}</div>
        </div>
      )}

      {/* Amounts */}
      {amountFields.length > 0 && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: `repeat(${amountFields.length}, 1fr)`,
          gap: 12,
          marginBottom: 32,
        }}>
          {amountFields.map((f) => (
            <div key={f.label} className="card" style={{ padding: 14, textAlign: 'center' }}>
              <div className="mono-sm" style={{ color: 'var(--gray-400)', marginBottom: 4 }}>{f.label}</div>
              <div className="mono" style={{ fontSize: '1.125rem', fontWeight: 600 }}>
                {f.prefix}{Number(f.value).toLocaleString('en-IN')}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── SECTION 2: Evidence — Where the data came from ── */}
      <div style={{ marginBottom: 40 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
          <div style={{
            width: 28, height: 28, background: 'var(--black)', color: 'var(--white)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            borderRadius: 'var(--radius-sm)', fontWeight: 600, fontSize: '0.8125rem',
          }}>1</div>
          <h2 className="heading-md">Evidence Source</h2>
        </div>
        <p className="body-sm" style={{ color: 'var(--gray-500)', marginBottom: 16 }}>
          Raw data from uploaded CSVs that triggered this flag.
        </p>

        {evidence.reasoning && (
          <div className="card" style={{ padding: 16, marginBottom: 12, borderLeft: '3px solid var(--gray-300)' }}>
            <div className="mono-sm" style={{ color: 'var(--gray-400)', marginBottom: 6 }}>Flag Reasoning</div>
            <div className="markdown-content body-sm">
              <ReactMarkdown>{evidence.reasoning}</ReactMarkdown>
            </div>
          </div>
        )}

        {evidence.classification && (
          <div className="card" style={{ padding: 16, marginBottom: 12, borderLeft: '3px solid var(--gray-300)' }}>
            <div className="mono-sm" style={{ color: 'var(--gray-400)', marginBottom: 6 }}>Pattern Classification</div>
            <div className="markdown-content body-sm">
              <ReactMarkdown>{evidence.classification}</ReactMarkdown>
            </div>
          </div>
        )}

        {rawSources.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {rawSources.map((src) => (
              <div key={src.name} className="card" style={{ padding: 16 }}>
                <div className="mono-sm" style={{ color: 'var(--gray-400)', marginBottom: 6 }}>
                  Source: {src.name} CSV
                </div>
                <div className="body-sm mono" style={{ fontSize: '0.8125rem', color: 'var(--gray-600)', lineHeight: 1.6 }}>
                  {src.content}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── SECTION 3: Legal Route — What actions can be taken ── */}
      <div style={{ marginBottom: 40 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
          <div style={{
            width: 28, height: 28, background: 'var(--black)', color: 'var(--white)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            borderRadius: 'var(--radius-sm)', fontWeight: 600, fontSize: '0.8125rem',
          }}>2</div>
          <h2 className="heading-md">Legal Route &amp; Suggestions</h2>
        </div>
        <p className="body-sm" style={{ color: 'var(--gray-500)', marginBottom: 16 }}>
          Applicable legal framework and recommended actions for this pattern.
        </p>

        {evidence.legal ? (
          <div className="card" style={{ padding: 20, lineHeight: 1.7 }}>
            <div className="markdown-content">
              <ReactMarkdown>{evidence.legal}</ReactMarkdown>
            </div>
          </div>
        ) : (
          <div className="card body-sm" style={{ padding: 16, color: 'var(--gray-400)' }}>
            No legal route data available for this work.
          </div>
        )}

        {data.legal_route && (
          <div className="card" style={{ padding: 16, marginTop: 12, borderLeft: '3px solid var(--black)' }}>
            <div className="mono-sm" style={{ color: 'var(--gray-400)', marginBottom: 4 }}>Applicable Legal Route</div>
            <div className="body-sm" style={{ fontWeight: 500 }}>{data.legal_route}</div>
          </div>
        )}
      </div>

      {/* ── SECTION 4: Human Verification — ML can't determine fraud alone ── */}
      <div style={{ marginBottom: 40 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
          <div style={{
            width: 28, height: 28, background: 'var(--black)', color: 'var(--white)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            borderRadius: 'var(--radius-sm)', fontWeight: 600, fontSize: '0.8125rem',
          }}>3</div>
          <h2 className="heading-md">Human Verification</h2>
        </div>

        <div className="card" style={{
          padding: 20, marginBottom: 16,
          borderLeft: '3px solid var(--gray-300)',
          background: 'var(--gray-50)',
        }}>
          <p className="body-sm" style={{ color: 'var(--gray-600)', fontStyle: 'italic', lineHeight: 1.7 }}>
            A flag is a <strong>lead for review, not a verdict</strong>. Machine learning models
            can identify statistical anomalies and pattern matches, but cannot determine fraud
            from text alone. Before treating this as fraud, a human reviewer must verify the
            findings against ground-truth records.
          </p>
        </div>

        {/* Possible legitimate explanations */}
        {evidence.explanations && (
          <div className="card" style={{ padding: 20, marginBottom: 16 }}>
            <div className="heading-sm" style={{ marginBottom: 12 }}>Possible Legitimate Explanations</div>
            <div className="markdown-content body-sm">
              <ReactMarkdown>{evidence.explanations}</ReactMarkdown>
            </div>
          </div>
        )}

        {/* Verification checklist */}
        {evidence.checklist && (
          <div className="card" style={{ padding: 20, borderLeft: '3px solid var(--black)' }}>
            <div className="heading-sm" style={{ marginBottom: 12 }}>Verification Checklist</div>
            <div className="markdown-content body-sm">
              <ReactMarkdown>{evidence.checklist}</ReactMarkdown>
            </div>
          </div>
        )}

        {/* Verdict selector */}
        <div className="card" style={{ padding: 20, marginTop: 16 }}>
          <div className="heading-sm" style={{ marginBottom: 12 }}>Mark Verdict</div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {[
              { value: 'pending', label: 'Pending Review', style: 'badge-default' },
              { value: 'legitimate', label: 'Legitimate', style: 'badge-info' },
              { value: 'needs_flagging', label: 'Needs Flagging', style: 'badge-warning' },
              { value: 'refer', label: 'Refer to Authority', style: 'badge-danger' },
            ].map((v) => (
              <button
                key={v.value}
                className={`badge ${verdict === v.value ? v.style : 'badge-default'}`}
                style={{
                  padding: '6px 14px',
                  cursor: 'pointer',
                  border: verdict === v.value ? '2px solid var(--black)' : '2px solid transparent',
                  fontSize: '0.8125rem',
                }}
                onClick={() => setVerdict(v.value)}
              >
                {v.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Footer disclaimer */}
      <div style={{
        padding: '16px 20px', background: 'var(--gray-50)',
        borderRadius: 'var(--radius-md)', boxShadow: 'var(--shadow-border)',
        marginBottom: 32,
      }}>
        <p className="body-sm" style={{ color: 'var(--gray-500)', lineHeight: 1.6 }}>
          Auto-generated dossier. Model does <strong>not</strong> issue legal conclusions.
          This analysis is for informational purposes only and does not constitute legal advice.
        </p>
      </div>
    </div>
  )
}
