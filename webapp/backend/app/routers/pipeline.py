"""Combined orchestrator. Reuses the exact same service functions as the standalone
endpoints and streams progress over Server-Sent Events."""
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from ..db import get_conn
from ..services import chain as chain_service
from ..services import face as face_service
from ..services import search as search_service
from ..services import verify as verify_service

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/run")
async def run(image: UploadFile = File(...),
              match_selection: str = Form("auto"),
              use_real_blockchain: bool = Form(False)):
    raw = await image.read()
    if not raw:
        raise HTTPException(400, "Empty upload.")
    original_name = image.filename or "upload.jpg"
    selection: str | int = match_selection
    if isinstance(selection, str) and selection.isdigit():
        selection = int(selection)

    def event_stream():
        conn = get_conn()
        run_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO pipeline_runs (id, status, created_at) VALUES (?, 'running', ?)",
            (run_id, now),
        )
        conn.commit()
        face_id = search_id = block_id = None
        try:
            # ---- Stage 1: face encode ----
            yield _sse("stage_start", {"stage": "face_encode"})
            image_path = face_service.save_upload(raw, original_name)
            enc = face_service.detect_and_encode(image_path)
            face_result = face_service.persist_face(conn, image_path, enc)
            face_id = face_result["face_id"]
            conn.execute("UPDATE pipeline_runs SET face_id = ? WHERE id = ?", (face_id, run_id))
            conn.commit()
            yield _sse("stage_complete", {"stage": "face_encode", "result": face_result})

            # ---- Stage 2: search ----
            yield _sse("stage_start", {"stage": "search"})
            search_result = search_service.run_and_persist(conn, face_id, image_path, selection)
            search_id = search_result["search_id"]
            conn.execute("UPDATE pipeline_runs SET search_id = ? WHERE id = ?", (search_id, run_id))
            conn.commit()
            yield _sse("stage_complete", {"stage": "search", "result": search_result})

            # ---- Stage 3: chain add ----
            yield _sse("stage_start", {"stage": "chain_add"})
            block_result = chain_service.add_block(
                conn, face_id, search_id, None, use_real_blockchain
            )
            block_id = block_result["block_id"]
            conn.execute("UPDATE pipeline_runs SET block_id = ? WHERE id = ?", (block_id, run_id))
            conn.commit()
            yield _sse("stage_complete", {"stage": "chain_add", "result": block_result})

            # ---- Stage 4: verify ----
            yield _sse("stage_start", {"stage": "verify"})
            verify_result = verify_service.verify_block(conn, block_id)
            yield _sse("stage_complete", {"stage": "verify", "result": verify_result})

            conn.execute("UPDATE pipeline_runs SET status = 'done' WHERE id = ?", (run_id,))
            conn.commit()
            yield _sse("done", {
                "run_id": run_id, "face_id": face_id,
                "search_id": search_id, "block_id": block_id,
            })
        except (face_service.FaceError, search_service.SearchError,
                chain_service.ChainError) as e:
            stage = {"FaceError": "face_encode", "SearchError": "search",
                     "ChainError": "chain_add"}[type(e).__name__]
            conn.execute(
                "UPDATE pipeline_runs SET status = 'error', error_stage = ?, error_message = ? WHERE id = ?",
                (stage, str(e), run_id),
            )
            conn.commit()
            yield _sse("error", {"stage": stage, "reason": str(e)})
        except Exception as e:  # noqa: BLE001
            conn.execute(
                "UPDATE pipeline_runs SET status = 'error', error_stage = 'unknown', error_message = ? WHERE id = ?",
                (str(e), run_id),
            )
            conn.commit()
            yield _sse("error", {"stage": "unknown", "reason": str(e)})
        finally:
            conn.close()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no",
                 "Connection": "keep-alive"},
    )


@router.post("/register")
def register_run(face_id: str = Form(...), search_id: str = Form(...),
                 block_id: str = Form(...)):
    """Record a step-by-step run (face/search/chain done individually) as one
    pipeline_runs row so it shows up in the ledger alongside full-pipeline runs."""
    conn = get_conn()
    try:
        run_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """INSERT INTO pipeline_runs (id, face_id, search_id, block_id, status, created_at)
               VALUES (?, ?, ?, ?, 'done', ?)""",
            (run_id, face_id, search_id, block_id, now),
        )
        conn.commit()
        return {"run_id": run_id}
    finally:
        conn.close()


@router.get("/{run_id}")
def get_run(run_id: str):
    conn = get_conn()
    try:
        run = conn.execute("SELECT * FROM pipeline_runs WHERE id = ?", (run_id,)).fetchone()
        if run is None:
            raise HTTPException(404, "run not found")
        out = dict(run)
        if run["face_id"]:
            face = conn.execute("SELECT * FROM faces WHERE id = ?", (run["face_id"],)).fetchone()
            d = dict(face)
            d["thumbnail_url"] = f"/uploads/{d['image_path'].rsplit('/', 1)[-1]}"
            out["face"] = d
        if run["search_id"]:
            s = dict(conn.execute("SELECT * FROM searches WHERE id = ?", (run["search_id"],)).fetchone())
            s["raw_response"] = json.loads(s["raw_response"])
            out["search"] = s
        if run["block_id"]:
            out["block"] = dict(conn.execute("SELECT * FROM blocks WHERE id = ?", (run["block_id"],)).fetchone())
        return out
    finally:
        conn.close()
