import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { api, runPipeline } from '../api'
import StatusBadge from '../components/StatusBadge'
import { Hash } from '../components/Hash'

const STAGES = [
  { key: 'face_encode', title: '1 · Face encoding', desc: 'Detect & embed the face' },
  { key: 'search', title: '2 · Reverse-image search', desc: 'Find a matching post online' },
  { key: 'chain_add', title: '3 · Blockchain add', desc: 'Append a hash-linked block' },
  { key: 'verify', title: '4 · Verification', desc: 'Recompute & compare every hash' },
]

export default function RunPage() {
  const { state } = useLocation()
  const navigate = useNavigate()
  const file = state?.file
  const mode = state?.mode || 'full'

  if (!file) {
    return (
      <div className="page page--narrow">
        <p className="page__lead">No image in progress.</p>
        <Link className="btn btn--primary" to="/">← Start a new run</Link>
      </div>
    )
  }
  return mode === 'full'
    ? <FullRun file={file} useReal={state?.useRealBlockchain} navigate={navigate} />
    : <StepRun file={file} useReal={state?.useRealBlockchain} navigate={navigate} />
}

/* ---------------- full pipeline (SSE) ---------------- */
function FullRun({ file, useReal, navigate }) {
  const [stageState, setStageState] = useState(
    Object.fromEntries(STAGES.map((s) => [s.key, { status: 'pending', result: null }])),
  )
  const [error, setError] = useState(null)
  const [done, setDone] = useState(null)
  const startedRef = useRef(false)

  useEffect(() => {
    // Start exactly once. We deliberately do NOT abort on effect cleanup:
    // React 18 StrictMode mounts → cleans up → re-mounts effects in dev, and an
    // abort there would cancel the upload before the request is even sent
    // (symptom: every stage stuck on "pending", zero backend hits). A local
    // pipeline run finishes in a few seconds, so there's nothing to cancel.
    if (startedRef.current) return
    startedRef.current = true
    runPipeline(
      file,
      { matchSelection: 'auto', useRealBlockchain: !!useReal },
      (ev, data) => {
        if (ev === 'stage_start') {
          setStageState((p) => ({ ...p, [data.stage]: { ...p[data.stage], status: 'running' } }))
        } else if (ev === 'stage_complete') {
          setStageState((p) => ({ ...p, [data.stage]: { status: 'done', result: data.result } }))
        } else if (ev === 'error') {
          setError(data)
          setStageState((p) => ({ ...p, [data.stage]: { ...(p[data.stage] || {}), status: 'error' } }))
        } else if (ev === 'done') {
          setDone(data)
        }
      },
    )
  }, [file, useReal])

  const previewUrl = URL.createObjectURL(file)

  return (
    <div className="page">
      <div className="runhead">
        <div>
          <h1 className="page__title">Live run</h1>
          <p className="page__lead">Four stages, streamed from the server as they complete.</p>
        </div>
        <img src={previewUrl} alt="" className="runhead__thumb" />
      </div>

      {error && (
        <div className="alert alert--bad">
          <strong>Stopped at “{error.stage}”.</strong> {error.reason}
          <Link to="/" className="btn btn--ghost btn--sm">Try another image</Link>
        </div>
      )}

      <div className="stagegrid">
        {STAGES.map((s) => {
          const st = stageState[s.key]
          return (
            <div key={s.key} className={`stagecard stagecard--${st.status}`}>
              <div className="stagecard__head">
                <div>
                  <div className="stagecard__title">{s.title}</div>
                  <div className="stagecard__desc">{s.desc}</div>
                </div>
                <StatusBadge status={st.status === 'done' ? 'verified' : st.status} />
              </div>
              {st.result && <StageResult stage={s.key} result={st.result} />}
            </div>
          )
        })}
      </div>

      {done && (
        <div className="alert alert--ok">
          <strong>Pipeline complete.</strong> Block committed to the chain.
          <div className="alert__actions">
            <button className="btn btn--primary btn--sm" onClick={() => navigate(`/record/${done.run_id}`)}>
              Open record detail →
            </button>
            <Link className="btn btn--ghost btn--sm" to="/ledger">View ledger</Link>
          </div>
        </div>
      )}
    </div>
  )
}

function StageResult({ stage, result }) {
  if (stage === 'face_encode') {
    return (
      <dl className="kv">
        <div><dt>Method</dt><dd>{result.encoding_method}</dd></div>
        <div><dt>Image hash</dt><dd><Hash value={result.image_hash} /></dd></div>
        <div><dt>Encoding hash</dt><dd><Hash value={result.encoding_hash} /></dd></div>
      </dl>
    )
  }
  if (stage === 'search') {
    const m = result.matched_post
    return (
      <div className="kv">
        <div><dt>Engine</dt><dd>{result.engine_used}</dd></div>
        <div><dt>Matched</dt><dd><a href={m.url} target="_blank" rel="noreferrer">{m.title}</a><br /><span className="muted">{m.source}</span></dd></div>
        <div><dt>Why</dt><dd className="muted">{result.selection_reason}</dd></div>
        <div><dt>Post hash</dt><dd><Hash value={result.post_hash} /></dd></div>
      </div>
    )
  }
  if (stage === 'chain_add') {
    return (
      <dl className="kv">
        <div><dt>Block #</dt><dd>{result.block_index}</dd></div>
        <div><dt>Prev hash</dt><dd><Hash value={result.prev_hash} /></dd></div>
        <div><dt>Block hash</dt><dd><Hash value={result.block_hash} /></dd></div>
        {result.tx_hash && (
          <div><dt>Sepolia tx</dt><dd><a href={result.etherscan_url} target="_blank" rel="noreferrer">{result.tx_hash}</a></dd></div>
        )}
      </dl>
    )
  }
  if (stage === 'verify') {
    return (
      <div className="fieldpills">
        {Object.entries(result.field_matches).map(([k, ok]) => (
          <span key={k} className={`fieldpill ${ok ? 'fieldpill--ok' : 'fieldpill--bad'}`}>
            {k.replace('_', ' ')} {ok ? '✓' : '✗'}
          </span>
        ))}
      </div>
    )
  }
  return null
}

/* ---------------- step by step ---------------- */
function StepRun({ file, useReal, navigate }) {
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  const [face, setFace] = useState(null)
  const [search, setSearch] = useState(null)
  const [matchIdx, setMatchIdx] = useState(0)
  const [block, setBlock] = useState(null)
  const [verify, setVerify] = useState(null)
  const [runId, setRunId] = useState(null)

  async function guard(fn) {
    setBusy(true); setErr(null)
    try { await fn() } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }

  return (
    <div className="page">
      <h1 className="page__title">Step by step</h1>
      <p className="page__lead">Run each stage yourself and inspect its output before continuing.</p>
      {err && <div className="alert alert--bad">{err}</div>}

      <ol className="steplist">
        <li className={face ? 'done' : ''}>
          <div className="steplist__head">
            <span>1 · Encode face</span>
            {!face && <button className="btn btn--primary btn--sm" disabled={busy}
              onClick={() => guard(async () => setFace(await api.encodeFace(file)))}>Run</button>}
            {face && <StatusBadge status="verified" />}
          </div>
          {face && (
            <dl className="kv">
              <div><dt>face_id</dt><dd><Hash value={face.face_id} /></dd></div>
              <div><dt>Method</dt><dd>{face.encoding_method}</dd></div>
              <div><dt>Image hash</dt><dd><Hash value={face.image_hash} /></dd></div>
            </dl>
          )}
        </li>

        <li className={search ? 'done' : ''}>
          <div className="steplist__head">
            <span>2 · Reverse-image search</span>
            {face && !search && <button className="btn btn--primary btn--sm" disabled={busy}
              onClick={() => guard(async () => {
                const r = await api.search(face.face_id, 'auto')
                setSearch(r); setMatchIdx(r.selected_index)
              })}>Run</button>}
            {search && <StatusBadge status="verified" />}
          </div>
          {search && (
            <div className="matchlist">
              {search.matches.map((m, i) => (
                <label key={i} className={`matchopt ${i === matchIdx ? 'is-sel' : ''}`}>
                  <input type="radio" name="match" checked={i === matchIdx} onChange={() => setMatchIdx(i)} />
                  <div>
                    <a href={m.url} target="_blank" rel="noreferrer">{m.title}</a>
                    <div className="muted">{m.source}</div>
                  </div>
                </label>
              ))}
              <div className="muted small">{search.selection_reason}</div>
            </div>
          )}
        </li>

        <li className={block ? 'done' : ''}>
          <div className="steplist__head">
            <span>3 · Add block to chain</span>
            {search && !block && <button className="btn btn--primary btn--sm" disabled={busy}
              onClick={() => guard(async () =>
                setBlock(await api.chainAdd(face.face_id, search.search_id, matchIdx, !!useReal)))}>Run</button>}
            {block && <StatusBadge status="verified" />}
          </div>
          {block && (
            <dl className="kv">
              <div><dt>Block #</dt><dd>{block.block_index}</dd></div>
              <div><dt>Prev hash</dt><dd><Hash value={block.prev_hash} /></dd></div>
              <div><dt>Block hash</dt><dd><Hash value={block.block_hash} /></dd></div>
            </dl>
          )}
        </li>

        <li className={verify ? 'done' : ''}>
          <div className="steplist__head">
            <span>4 · Verify block</span>
            {block && !verify && <button className="btn btn--primary btn--sm" disabled={busy}
              onClick={() => guard(async () => {
                setVerify(await api.verifyBlock(block.block_id))
                const r = await api.registerRun(face.face_id, search.search_id, block.block_id)
                setRunId(r.run_id)
              })}>Run</button>}
            {verify && <StatusBadge status={verify.valid ? 'verified' : 'tampered'} />}
          </div>
          {verify && (
            <div className="fieldpills">
              {Object.entries(verify.field_matches).map(([k, ok]) => (
                <span key={k} className={`fieldpill ${ok ? 'fieldpill--ok' : 'fieldpill--bad'}`}>
                  {k.replace('_', ' ')} {ok ? '✓' : '✗'}
                </span>
              ))}
            </div>
          )}
        </li>
      </ol>

      {verify && (
        <div className="alert alert--ok">
          <strong>All four stages done.</strong>
          <div className="alert__actions">
            {runId && <button className="btn btn--primary btn--sm" onClick={() => navigate(`/record/${runId}`)}>Open record detail →</button>}
            <Link className="btn btn--ghost btn--sm" to="/ledger">View ledger</Link>
          </div>
        </div>
      )}
    </div>
  )
}
