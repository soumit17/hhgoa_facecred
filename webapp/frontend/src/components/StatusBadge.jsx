// One badge component shared by the SSE stage cards and the verification screen.
// pending = gray, running = subtle pulse, verified = green, tampered = red.

const LABELS = {
  pending: 'Pending',
  running: 'Running',
  done: 'Done',
  verified: 'Verified',
  tampered: 'Tampered',
  incomplete: 'Incomplete',
  error: 'Error',
}

export default function StatusBadge({ status, children }) {
  const s = status || 'pending'
  return (
    <span className={`badge badge--${s}`}>
      <span className="badge__dot" />
      {children || LABELS[s] || s}
    </span>
  )
}
