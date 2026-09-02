import { Routes, Route } from 'react-router-dom'
import ErrorBoundary from './components/ErrorBoundary'
import Layout from './components/Layout'
import Upload from './pages/Upload'
import Results from './pages/Results'
import MpRankings from './pages/MpRankings'
import WorkDetail from './pages/WorkDetail'
import Similarity from './pages/Similarity'

export default function App() {
  return (
    <ErrorBoundary>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Upload />} />
          <Route path="/results" element={<Results />} />
          <Route path="/mp-rankings" element={<MpRankings />} />
          <Route path="/works/:id" element={<WorkDetail />} />
          <Route path="/similarity" element={<Similarity />} />
        </Route>
      </Routes>
    </ErrorBoundary>
  )
}
