import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import SearchPage from './pages/SearchPage'
import SuburbPage from './pages/SuburbPage'
import RankingsPage from './pages/RankingsPage'
import MapPage from './pages/MapPage'
import ComparePage from './pages/ComparePage'

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/"         element={<SearchPage />} />
          <Route path="/suburb/:id" element={<SuburbPage />} />
          <Route path="/rankings" element={<RankingsPage />} />
          <Route path="/map"      element={<MapPage />} />
          <Route path="/compare"  element={<ComparePage />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}
