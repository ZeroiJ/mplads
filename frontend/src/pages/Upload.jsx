import { useState, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { uploadCSVs } from '../api'

const FILE_KEYS = [
  { key: 'works_recommended', label: 'Works Recommended.csv', required: true },
  { key: 'works_sanctioned', label: 'Works Sanctioned.csv', required: true },
  { key: 'works_completed', label: 'Works Completed.csv', required: true },
  { key: 'expenditure', label: 'Expenditure on Completed and On-going Works.csv', required: true },
]

export default function Upload() {
  const navigate = useNavigate()
  const [files, setFiles] = useState({})
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const inputRefs = useRef({})

  const allLoaded = FILE_KEYS.every((f) => files[f.key])

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setDragging(false)
    const dropped = Array.from(e.dataTransfer.files)
    const csvs = dropped.filter((f) => f.name.endsWith('.csv'))
    if (csvs.length === 0) return

    setFiles((prev) => {
      const next = { ...prev }
      for (const csv of csvs) {
        const match = FILE_KEYS.find((f) => f.label === csv.name)
        if (match) next[match.key] = csv
      }
      return next
    })
  }, [])

  const handleFileChange = (key, file) => {
    if (file) setFiles((prev) => ({ ...prev, [key]: file }))
  }

  const handleUpload = async () => {
    if (!allLoaded) return
    setUploading(true)
    setError(null)
    try {
      const res = await uploadCSVs(files)
      setResult(res)
      setTimeout(() => navigate('/results'), 1200)
    } catch (err) {
      setError(err.message)
    } finally {
      setUploading(false)
    }
  }

  const handleSampleData = async () => {
    setUploading(true)
    setError(null)
    try {
      const sampleFiles = {}
      for (const f of FILE_KEYS) {
        const res = await fetch(`/sample/${f.label}`)
        if (!res.ok) throw new Error(`Sample file not found: ${f.label}`)
        const blob = await res.blob()
        sampleFiles[f.key] = new File([blob], f.label, { type: 'text/csv' })
      }
      const res = await uploadCSVs(sampleFiles)
      setResult(res)
      setTimeout(() => navigate('/results'), 1200)
    } catch (err) {
      setError(err.message)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="container page">
      <div style={{ maxWidth: 640, margin: '0 auto' }}>
        <h1 className="heading-display" style={{ marginBottom: 8 }}>
          Detect fraud patterns
        </h1>
        <p className="body-lg" style={{ color: 'var(--gray-500)', marginBottom: 40 }}>
          Upload raw MPLADS CSVs. The system computes results live from your files.
        </p>

        <div
          className={`upload-zone ${dragging ? 'upload-zone-active' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          onClick={() => inputRefs.current[FILE_KEYS[0].key]?.click()}
        >
          <div style={{ marginBottom: 16 }}>
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12" />
            </svg>
          </div>
          <p className="heading-sm" style={{ marginBottom: 4 }}>
            Drop 4 CSV files here
          </p>
          <p className="body-sm" style={{ color: 'var(--gray-400)' }}>
            or click to browse
          </p>
        </div>

        <div style={{ marginTop: 24 }}>
          {FILE_KEYS.map((f) => (
            <div
              key={f.key}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '10px 16px',
                boxShadow: 'var(--shadow-border)',
                borderRadius: 'var(--radius-md)',
                marginBottom: 8,
                background: files[f.key] ? 'var(--gray-50)' : 'var(--white)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{
                  width: 8, height: 8, borderRadius: '50%',
                  background: files[f.key] ? 'var(--black)' : 'var(--gray-200)',
                  flexShrink: 0,
                }} />
                <span className="body-sm mono" style={{ fontSize: '0.8125rem' }}>
                  {f.label}
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                {files[f.key] && (
                  <span className="body-sm" style={{ color: 'var(--gray-400)' }}>
                    {(files[f.key].size / 1024).toFixed(0)} KB
                  </span>
                )}
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={(e) => {
                    e.stopPropagation()
                    inputRefs.current[f.key]?.click()
                  }}
                >
                  {files[f.key] ? 'Change' : 'Browse'}
                </button>
                <input
                  ref={(el) => (inputRefs.current[f.key] = el)}
                  type="file"
                  accept=".csv"
                  style={{ display: 'none' }}
                  onChange={(e) => handleFileChange(f.key, e.target.files[0])}
                />
              </div>
            </div>
          ))}
        </div>

        {error && (
          <div style={{
            marginTop: 16,
            padding: '12px 16px',
            background: '#f8d7da',
            color: '#842029',
            borderRadius: 'var(--radius-md)',
            fontSize: '0.875rem',
          }}>
            {error}
          </div>
        )}

        {result && (
          <div style={{
            marginTop: 16,
            padding: '12px 16px',
            background: '#d1e7dd',
            color: '#0f5132',
            borderRadius: 'var(--radius-md)',
            fontSize: '0.875rem',
          }}>
            Processed {result.works} works, {result.flagged} flagged. Redirecting...
          </div>
        )}

        <div style={{ marginTop: 24, display: 'flex', gap: 12 }}>
          <button
            className="btn btn-primary btn-lg"
            disabled={!allLoaded || uploading}
            onClick={handleUpload}
            style={{ flex: 1 }}
          >
            {uploading ? 'Running detection...' : 'Run Detection'}
          </button>
          <button
            className="btn btn-secondary btn-lg"
            disabled={uploading}
            onClick={handleSampleData}
          >
            Use sample data
          </button>
        </div>
      </div>
    </div>
  )
}
