import { useEffect, useState } from 'react'
import { NavLink, Route, Routes } from 'react-router-dom'
import { api } from './api'
import UploadPage from './pages/UploadPage'
import RunPage from './pages/RunPage'
import LedgerPage from './pages/LedgerPage'
import RecordPage from './pages/RecordPage'

export default function App() {
  const [health, setHealth] = useState(null)
  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth({ ok: false }))
  }, [])

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand__mark">◆</span>
          <div>
            <div className="brand__name">FaceChain</div>
            <div className="brand__sub">Identity &amp; Blockchain Verification</div>
          </div>
        </div>
        <nav className="nav">
          <NavLink to="/" end className="nav__link">Start</NavLink>
          <NavLink to="/ledger" className="nav__link">Ledger</NavLink>
        </nav>
        <div className="topbar__status">
          {health == null ? (
            <span className="dot dot--idle" />
          ) : health.ok ? (
            <span className="pill pill--ok">
              API online{health.serpapi_key_set ? '' : ' · no SerpApi key'}
            </span>
          ) : (
            <span className="pill pill--bad">API offline</span>
          )}
        </div>
      </header>

      <main className="main">
        <Routes>
          <Route path="/" element={<UploadPage />} />
          <Route path="/run/:runId?" element={<RunPage />} />
          <Route path="/ledger" element={<LedgerPage />} />
          <Route path="/record/:runId" element={<RecordPage />} />
        </Routes>
      </main>

      <footer className="footer">
        HH Goa 2026 · Task 3 — face scan → live reverse-image search → hash-linked chain,
        verified live on every read.
      </footer>
    </div>
  )
}
