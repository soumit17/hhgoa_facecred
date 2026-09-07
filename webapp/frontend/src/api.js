// Thin fetch wrapper. All URLs are same-origin relative (dev server proxies to :8000).

async function jsonFetch(url, opts) {
  const res = await fetch(url, opts)
  const text = await res.text()
  const data = text ? JSON.parse(text) : null
  if (!res.ok) {
    const msg = data?.detail || data?.reason || res.statusText
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg))
  }
  return data
}

export const api = {
  health: () => jsonFetch('/api/health'),

  listRecords: () => jsonFetch('/api/view/records'),
  recordDetail: (runId) => jsonFetch(`/api/view/records/${runId}`),

  chain: () => jsonFetch('/api/chain'),
  getRun: (runId) => jsonFetch(`/api/pipeline/${runId}`),

  // Step-by-step endpoints
  encodeFace: (file) => {
    const fd = new FormData()
    fd.append('image', file)
    return jsonFetch('/api/face/encode', { method: 'POST', body: fd })
  },
  search: (faceId, matchSelection = 'auto') =>
    jsonFetch('/api/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ face_id: faceId, match_selection: matchSelection }),
    }),
  chainAdd: (faceId, searchId, matchIndex, useRealBlockchain = false) =>
    jsonFetch('/api/chain/add', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        face_id: faceId,
        search_id: searchId,
        match_index: matchIndex ?? null,
        use_real_blockchain: useRealBlockchain,
      }),
    }),
  verifyBlock: (blockId) =>
    jsonFetch(`/api/chain/verify/${blockId}`, { method: 'POST' }),
  registerRun: (faceId, searchId, blockId) => {
    const fd = new FormData()
    fd.append('face_id', faceId)
    fd.append('search_id', searchId)
    fd.append('block_id', blockId)
    return jsonFetch('/api/pipeline/register', { method: 'POST', body: fd })
  },
}

// Runs the SSE pipeline. Calls onEvent(eventName, dataObject) for every server event.
export function runPipeline(file, { matchSelection = 'auto', useRealBlockchain = false }, onEvent) {
  const fd = new FormData()
  fd.append('image', file)
  fd.append('match_selection', String(matchSelection))
  fd.append('use_real_blockchain', String(useRealBlockchain))

  const controller = new AbortController()
  ;(async () => {
    try {
      const res = await fetch('/api/pipeline/run', {
        method: 'POST',
        body: fd,
        signal: controller.signal,
      })
      if (!res.ok || !res.body) {
        const t = await res.text()
        onEvent('error', { stage: 'request', reason: t || res.statusText })
        return
      }
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const chunks = buffer.split('\n\n')
        buffer = chunks.pop() || ''
        for (const chunk of chunks) {
          const evLine = chunk.split('\n').find((l) => l.startsWith('event:'))
          const dataLine = chunk.split('\n').find((l) => l.startsWith('data:'))
          if (!evLine || !dataLine) continue
          const ev = evLine.slice(6).trim()
          const data = JSON.parse(dataLine.slice(5).trim())
          onEvent(ev, data)
        }
      }
    } catch (e) {
      if (e.name !== 'AbortError') onEvent('error', { stage: 'stream', reason: e.message })
    }
  })()

  return () => controller.abort()
}
