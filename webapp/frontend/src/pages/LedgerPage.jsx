import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'
import StatusBadge from '../components/StatusBadge'

export default function LedgerPage() {
  const [records, setRecords] = useState(null)
  const [err, setErr] = useState(null)
  const navigate = useNavigate()

  async function load() {
    try {
      const r = await api.listRecords()
      setRecords(r.records)
      setErr(null)
    } catch (e) {
      setErr(e.message)
    }
  }

  useEffect(() => {
    load()
    const t = setInterval(load, 4000) // live: reflects a tamper within 4s, no refresh
    return () => clearInterval(t)
  }, [])

  const tamperedCount = records?.filter((r) => r.overall_status === 'tampered').length || 0

  return (
    <div className="page">
      <div className="ledgerhead">
        <div>
          <h1 className="page__title">Ledger</h1>
          <p className="page__lead">
            One row per pipeline run. Status is recomputed live every 4 seconds —
            no stored verdicts. Tamper a row in the DB and it flips here on its own.
          </p>
        </div>
        <Link className="btn btn--primary" to="/">+ New run</Link>
      </div>

      {err && <div className="alert alert--bad">{err}</div>}
      {tamperedCount > 0 && (
        <div className="alert alert--bad">
          {tamperedCount} record{tamperedCount > 1 ? 's' : ''} failing verification.
        </div>
      )}

      <div className="tablewrap">
        <table className="table">
          <thead>
            <tr>
              <th>Block</th>
              <th>Run</th>
              <th>Matched post</th>
              <th>Created</th>
              <th>Chain link</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {records == null && (
              <tr><td colSpan="6" className="muted">Loading…</td></tr>
            )}
            {records?.length === 0 && (
              <tr><td colSpan="6" className="muted">No runs yet. Start one from “New run”.</td></tr>
            )}
            {records?.map((r) => (
              <tr
                key={r.run_id}
                className={`rowlink ${r.overall_status === 'tampered' ? 'row--bad' : ''}`}
                onClick={() => navigate(`/record/${r.run_id}`)}
              >
                <td className="mono">{r.block_index ?? '—'}</td>
                <td className="mono muted">{r.run_id.slice(0, 8)}</td>
                <td>{r.matched_post_title || <span className="muted">—</span>}</td>
                <td className="muted small">{new Date(r.created_at).toLocaleString()}</td>
                <td>
                  {r.chain_link_intact == null
                    ? <span className="muted">—</span>
                    : r.chain_link_intact
                      ? <span className="ok-text">intact</span>
                      : <span className="bad-text">broken</span>}
                </td>
                <td><StatusBadge status={r.overall_status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
