# FaceChain — Face Identification & Blockchain Verification web app

Web app version of `face_blockchain_pipeline.ipynb` (HH Goa 2026, Task 3).

**Pipeline:** face scan → live reverse-image search (find a matching post) → append a
tamper-evident fingerprint to a hash-linked chain → verification is **recomputed live
on every read**, so a direct DB edit is caught with no extra step.

- **Backend:** FastAPI + SQLite (`backend/`). Reuses the notebook's face-encoding,
  image-hosting, SerpApi search, and hash-chain logic as service modules.
- **Frontend:** React + Vite (`frontend/`), plain `fetch` + a manual SSE reader.
- **Tamper demo:** `tamper_demo.ipynb` — edits the DB directly with `sqlite3`,
  bypassing the app.

```
webapp/
├── backend/
│   ├── app/
│   │   ├── main.py            FastAPI app, routers, static frontend mount
│   │   ├── db.py  config.py   SQLite at backend/data/app.db (fixed path)
│   │   ├── schema.sql         faces / searches / blocks / pipeline_runs
│   │   ├── services/          face · search · chain · verify · hashing
│   │   └── routers/           /api/face /api/search /api/chain /api/pipeline /api/view
│   └── data/                  app.db + uploads/  (git-ignored, created on first run)
├── frontend/                  Vite React app (4 screens)
├── tamper_demo.ipynb          direct-DB tamper notebook
└── dev.sh                     starts backend + frontend together
```

---

## Prerequisites

- **Python 3.10+** and **Node.js 18+**
- A **SerpApi key** (free tier, 250 searches/month) — https://serpapi.com/manage-api-key

Put the key in an `.env` file. The backend reads `webapp/.env` first, then the repo
root `.env`:

```
# hhgoa_facecred/.env  (or webapp/.env)
SERPAPI_KEY=your_key_here

# only if you tick "Anchor on Sepolia testnet" in the UI:
SEPOLIA_RPC_URL=
WALLET_PRIVATE_KEY=
```

---

## Run it (development — two servers)

```bash
# 1. Backend
cd webapp/backend
python -m venv .venv && source .venv/bin/activate     # optional
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000

# 2. Frontend (new terminal)
cd webapp/frontend
npm install
npm run dev
```

Open **http://localhost:5173**. The Vite dev server proxies `/api` and `/uploads`
to the backend on `:8000`, so everything is same-origin.

Or start both at once:

```bash
cd webapp && ./dev.sh
```

`face_recognition` (dlib) can be slow/finicky to build on some machines. If it
won't install, the backend automatically falls back to an OpenCV Haar-cascade
detector + pixel-vector encoding — the pipeline still runs end to end.

## Run it (single server)

Build the frontend once; FastAPI then serves it at `/`:

```bash
cd webapp/frontend && npm install && npm run build
cd ../backend && pip install -r requirements.txt
python -m uvicorn app.main:app --port 8000
```

Open **http://localhost:8000**.

---

## The four screens

1. **Start** — pick a face image, choose *Run full pipeline* or *Step by step*,
   optional *Sepolia testnet* toggle.
2. **Live run** — four stage cards (face → search → chain → verify) driven by the
   `/api/pipeline/run` SSE stream; each reveals its result the moment it completes.
3. **Ledger** — one row per run, re-polled every 4 s with a **live-computed**
   green/red status. A broken chain link turns that row *and every later row* red.
4. **Record detail** — field-by-field badges (source image · face encoding ·
   matched post · block hash + chain link) with stored-vs-recomputed hashes.
   Auto re-verifies every 3 s plus a manual button.

---

## Demo: catch a tamper live

1. Run the pipeline **twice** in the UI (two different photos) so the chain has a
   middle block.
2. Open the **Ledger** screen and leave it visible.
3. Open `tamper_demo.ipynb` (run it from the `webapp/` directory so it finds
   `backend/data/app.db`) and run its cells — it does a raw
   `UPDATE searches SET matched_post_title = ...` on the **first** run, without
   touching any hash column.
4. Within a few seconds, with nobody touching the browser: block #0's row goes
   **red** (its stored `post_hash` no longer matches), and block #1 goes **red**
   too (`chain link broken`). Open either record to see exactly which field and
   its stored-vs-recomputed hash.
5. Run the notebook's last cell to restore the value; the rows go green again.

---

## API surface

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/face/encode` | multipart image → `faces` row |
| GET  | `/api/face/{id}` | stored face record |
| POST | `/api/search` | `{face_id}` → host image + SerpApi search → `searches` row |
| GET  | `/api/search/{id}` | stored search (replay, no quota burn) |
| POST | `/api/chain/add` | `{face_id, search_id, match_index?, use_real_blockchain?}` → new block |
| GET  | `/api/chain` | all blocks |
| POST | `/api/chain/verify/{block_id}` | live per-field recompute for one block |
| POST | `/api/pipeline/run` | image + form fields → **SSE** stream of all four stages |
| POST | `/api/pipeline/register` | records a step-by-step run in the ledger |
| GET  | `/api/pipeline/{run_id}` | consolidated past run |
| GET  | `/api/view/records` | ledger list, live status per run |
| GET  | `/api/view/records/{run_id}` | full field-by-field verification breakdown |

Interactive docs at **http://localhost:8000/docs**.

---

## Verification logic (recomputed every read — never cached)

1. **Image** — re-hash the file at `faces.image_path`, compare to `faces.image_hash`.
2. **Encoding** — re-hash `faces.encoding_vector` text, compare to `faces.encoding_hash`.
3. **Matched post** — re-hash `title + url + source`, compare to `searches.post_hash`.
4. **Block payload** — `sha256(image_hash + encoding_hash + post_hash)` from the
   *current* values above, compare to `blocks.payload_hash`.
5. **Block hash** — `sha256(prev_recomputed_hash + payload_hash)`, compare to
   `blocks.block_hash`.
6. **Chain link (cascade)** — each block's recomputed hash feeds the next block's
   check, so tampering a middle block flags every block after it too.
7. **On-chain (optional)** — if `use_real_blockchain`, compare the Sepolia tx
   `data` field to the stored `block_hash`.

---

## Known limitations (from the original notebook, still true)

- Reverse-image search only finds photos already indexed publicly online.
- SerpApi free tier: 250 searches/month — raw responses are stored so replays don't re-call.
- The OpenCV fallback encoding is a pixel vector, not a real face embedding.
- The image is briefly hosted on a free anonymous host (uguu.se → tmpfiles.org →
  catbox.moe) to get a public URL for the search API — only use images you may share.
