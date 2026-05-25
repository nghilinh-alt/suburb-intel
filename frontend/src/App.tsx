import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import SearchPage from './pages/SearchPage'
import SuburbPage from './pages/SuburbPage'
import RankingsPage from './pages/RankingsPage'

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<SearchPage />} />
          <Route path="/suburb/:id" element={<SuburbPage />} />
          <Route path="/rankings" element={<RankingsPage />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}
