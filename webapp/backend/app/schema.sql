-- Face Identification & Blockchain Verification — SQLite schema
-- Portable SQL only (no SQLite-only syntax) so it can move to Postgres later.
-- IMPORTANT: no cached is_valid / status columns anywhere. Verification is always
-- recomputed live at read time (see services/verify.py).

CREATE TABLE IF NOT EXISTS faces (
    id TEXT PRIMARY KEY,
    image_path TEXT NOT NULL,
    image_hash TEXT NOT NULL,          -- sha256 of image bytes
    encoding_vector TEXT NOT NULL,     -- JSON array, 128-d dlib vector or fallback vector
    encoding_hash TEXT NOT NULL,       -- sha256 of encoding_vector (the stored JSON text)
    encoding_method TEXT NOT NULL,     -- 'dlib' | 'opencv_fallback'
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS searches (
    id TEXT PRIMARY KEY,
    face_id TEXT NOT NULL REFERENCES faces(id),
    query_image_url TEXT NOT NULL,     -- the public URL handed to the search API
    raw_response TEXT NOT NULL,        -- full JSON response from SerpApi, stored for replay
    matched_post_title TEXT NOT NULL,
    matched_post_url TEXT NOT NULL,
    matched_post_source TEXT NOT NULL,
    post_hash TEXT NOT NULL,           -- sha256 of (title + url + source)
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS blocks (
    id TEXT PRIMARY KEY,
    block_index INTEGER NOT NULL,      -- 0, 1, 2... sequential position in the chain
    face_id TEXT NOT NULL REFERENCES faces(id),
    search_id TEXT NOT NULL REFERENCES searches(id),
    payload TEXT NOT NULL,             -- JSON: {image_hash, encoding_hash, post_hash}
    payload_hash TEXT NOT NULL,        -- sha256(image_hash + encoding_hash + post_hash)
    prev_hash TEXT NOT NULL,           -- block_hash of the previous block ('0'*64 for the first)
    block_hash TEXT NOT NULL,          -- sha256(prev_hash + payload_hash)
    use_real_blockchain INTEGER NOT NULL DEFAULT 0,
    tx_hash TEXT,                      -- Sepolia tx hash, null if local-only
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id TEXT PRIMARY KEY,
    face_id TEXT REFERENCES faces(id),
    search_id TEXT REFERENCES searches(id),
    block_id TEXT REFERENCES blocks(id),
    status TEXT NOT NULL,              -- 'running' | 'done' | 'error'
    error_stage TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL
);
