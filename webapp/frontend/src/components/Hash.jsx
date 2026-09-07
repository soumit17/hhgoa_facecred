import { useState } from 'react'

// Monospace hash display with click-to-copy and optional stored-vs-recomputed diff.
export function Hash({ value, title }) {
  const [copied, setCopied] = useState(false)
  if (!value) return <span className="hash hash--empty">—</span>
  return (
    <button
      className="hash"
      title={title || 'Click to copy'}
      onClick={() => {
        navigator.clipboard?.writeText(value)
        setCopied(true)
        setTimeout(() => setCopied(false), 900)
      }}
    >
      {copied ? 'copied ✓' : value}
    </button>
  )
}

export function HashCompare({ label, stored, recomputed }) {
  const match = stored === recomputed
  return (
    <div className={`hashcmp ${match ? 'hashcmp--ok' : 'hashcmp--bad'}`}>
      <div className="hashcmp__label">{label}</div>
      <div className="hashcmp__row">
        <span className="hashcmp__tag">stored</span>
        <Hash value={stored} />
      </div>
      <div className="hashcmp__row">
        <span className="hashcmp__tag">recomputed</span>
        <Hash value={recomputed} />
      </div>
      <div className="hashcmp__verdict">{match ? 'match' : 'MISMATCH'}</div>
    </div>
  )
}
