import { Component } from 'react'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    console.error('ErrorBoundary caught:', error, info)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="container page" style={{ maxWidth: 640 }}>
          <div className="card">
            <h2 className="heading-md" style={{ marginBottom: 12 }}>Something went wrong</h2>
            <pre className="mono" style={{
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              background: 'var(--gray-50)',
              padding: 16,
              borderRadius: 'var(--radius-md)',
              boxShadow: 'var(--shadow-border)',
              fontSize: '0.8125rem',
              marginBottom: 16,
            }}>
              {this.state.error.message}
            </pre>
            <button className="btn btn-primary" onClick={() => window.location.reload()}>
              Reload
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
