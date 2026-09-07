import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import StatusBadge from '../components/StatusBadge'
import { HashCompare } from '../components/Hash'

export default function RecordPage() {
  const { runId } = useParams()
  const [rec, setRec] = useState(null)
  const [err, setErr] = useState(null)
  const [lastChecked, setLastChecked] = useState(null)
  const [flash, setFlash] = useState(false)
  const prevStatus = useRef(null)

  const load = useCallback(async () => {
    try {
      const r = await api.recordDetail(runId)
      setErr(null)
      setLastChecked(new Date())
      if (prevStatus.current && prevStatus.current !== r.overall_status) {
        setFlash(true)
        setTimeout(() => setFlash(false), 1200)
      }
      prevStatus.current = r.overall_status
      setRec(r)
    } catch (e) {
      setErr(e.message)
    }
  }, [runId])

  useEffect(() => {
    load()
    const t = setInterval(load, 3000) // auto re-verify; badge flips live after a tamper
    return () => clearInterval(t)
  }, [load])

  if (err) return <div className="page"><div className="alert alert--bad">{err}</div><Link to="/ledger" className="btn btn--ghost">← Ledger</Link></div>
  if (!rec) return <div className="page"><p className="muted">Loading…</p></div>

  const f = rec.face
  const s = rec.search
  const b = rec.block

  return (
    <div className={`page ${flash ? 'page--flash' : ''}`}>
      <div className="rechead">
        <Link to="/ledger" className="back">← Ledger</Link>
        <div className="rechead__main">
          <h1 className="page__title">Record {runId.slice(0, 8)}</h1>
          <StatusBadge status={rec.overall_status}>
            {rec.overall_status === 'verified' ? 'All fields verified' : 'Tampering detected'}
          </StatusBadge>
        </div>
        <div className="rechead__meta">
          <button className="btn btn--ghost btn--sm" onClick={load}>Re-verify now</button>
          <span className="muted small">
            auto every 3s · last {lastChecked ? lastChecked.toLocaleTimeString() : '—'}
          </span>
        </div>
      </div>

      <div className="fieldgrid">
        <FieldCard title="Source image" status={f?.status}
          problems={f?.problems}>
          {f?.thumbnail_url && <img className="fieldcard__thumb" src={f.thumbnail_url} alt="" />}
          <HashCompare label="image bytes → sha256"
            stored={f?.stored_image_hash} recomputed={f?.recomputed_image_hash} />
        </FieldCard>

        <FieldCard title="Face encoding" status={f?.status}
          problems={f?.problems?.filter((p) => p.includes('encoding'))}>
          <div className="muted small">method: {f?.encoding_method}</div>
          <HashCompare label="encoding vector → sha256"
            stored={f?.stored_encoding_hash} recomputed={f?.recomputed_encoding_hash} />
        </FieldCard>

        <FieldCard title="Matched post" status={s?.status} problems={s?.problems}>
          {s?.matched_post && (
            <div className="postmeta">
              <a href={s.matched_post.url} target="_blank" rel="noreferrer">{s.matched_post.title}</a>
              <div className="muted small">{s.matched_post.source}</div>
            </div>
          )}
          <HashCompare label="title + url + source → sha256"
            stored={s?.stored_post_hash} recomputed={s?.recomputed_post_hash} />
        </FieldCard>

        <FieldCard title="Block & chain link" status={b?.status} problems={b?.problems}>
          <div className="muted small">block #{b?.block_index}</div>
          <HashCompare label="payload → sha256"
            stored={b?.stored_payload_hash} recomputed={b?.recomputed_payload_hash} />
          <HashCompare label="prev_hash + payload_hash → sha256"
            stored={b?.stored_block_hash} recomputed={b?.recomputed_block_hash} />
          <div className={`chainlink ${b?.chain_link_intact ? 'chainlink--ok' : 'chainlink--bad'}`}>
            <span>chain link</span>
            <strong>{b?.chain_link_intact ? 'intact' : 'BROKEN — this or an earlier block was altered'}</strong>
          </div>
          {b?.use_real_blockchain && (
            <div className="muted small">
              on-chain: {rec.onchain?.tx_hash
                ? <a href={`https://sepolia.etherscan.io/tx/${rec.onchain.tx_hash}`} target="_blank" rel="noreferrer">{rec.onchain.tx_hash.slice(0, 20)}…</a>
                : 'n/a'}
            </div>
          )}
        </FieldCard>
      </div>
    </div>
  )
}

function FieldCard({ title, status, problems, children }) {
  return (
    <div className={`fieldcard fieldcard--${status || 'pending'}`}>
      <div className="fieldcard__head">
        <span className="fieldcard__title">{title}</span>
        <StatusBadge status={status} />
      </div>
      <div className="fieldcard__body">{children}</div>
      {problems?.length > 0 && (
        <ul className="fieldcard__problems">
          {problems.map((p, i) => <li key={i}>{p}</li>)}
        </ul>
      )}
    </div>
  )
}
