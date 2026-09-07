import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

export default function UploadPage() {
  const navigate = useNavigate()
  const inputRef = useRef(null)
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [mode, setMode] = useState('full') // 'full' | 'steps'
  const [useReal, setUseReal] = useState(false)
  const [dragging, setDragging] = useState(false)

  function pick(f) {
    if (!f) return
    setFile(f)
    setPreview(URL.createObjectURL(f))
  }

  function start() {
    if (!file) return
    navigate('/run', { state: { file, mode, useRealBlockchain: useReal } })
  }

  return (
    <div className="page page--narrow">
      <h1 className="page__title">Run the pipeline</h1>
      <p className="page__lead">
        Upload a face photo. The pipeline detects and encodes the face, runs a live
        reverse-image search to find a matching post, then anchors a tamper-evident
        fingerprint on a hash-linked chain.
      </p>

      <div
        className={`dropzone ${dragging ? 'dropzone--active' : ''} ${preview ? 'dropzone--has' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault(); setDragging(false)
          pick(e.dataTransfer.files?.[0])
        }}
        onClick={() => inputRef.current?.click()}
      >
        {preview ? (
          <img src={preview} alt="preview" className="dropzone__img" />
        ) : (
          <>
            <div className="dropzone__icon">⬍</div>
            <div className="dropzone__text">Drop an image here or click to browse</div>
            <div className="dropzone__hint">JPG or PNG · a clear, front-facing photo works best</div>
          </>
        )}
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          hidden
          onChange={(e) => pick(e.target.files?.[0])}
        />
      </div>
      {file && <div className="filemeta">{file.name} · {(file.size / 1024).toFixed(0)} KB</div>}

      <div className="field">
        <div className="field__label">Mode</div>
        <div className="segmented">
          <button
            className={mode === 'full' ? 'is-active' : ''}
            onClick={() => setMode('full')}
          >
            Run full pipeline
          </button>
          <button
            className={mode === 'steps' ? 'is-active' : ''}
            onClick={() => setMode('steps')}
          >
            Step by step
          </button>
        </div>
      </div>

      <label className="checkrow">
        <input type="checkbox" checked={useReal} onChange={(e) => setUseReal(e.target.checked)} />
        <span>
          Anchor on the real Ethereum <strong>Sepolia testnet</strong>
          <span className="checkrow__hint"> — needs SEPOLIA_RPC_URL &amp; WALLET_PRIVATE_KEY on the backend</span>
        </span>
      </label>

      <button className="btn btn--primary btn--lg" disabled={!file} onClick={start}>
        {mode === 'full' ? 'Start pipeline →' : 'Begin step by step →'}
      </button>
    </div>
  )
}
