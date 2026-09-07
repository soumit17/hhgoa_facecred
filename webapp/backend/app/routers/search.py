from fastapi import APIRouter, Body, HTTPException

from ..db import get_conn
from ..services import search as search_service

router = APIRouter(prefix="/api/search", tags=["search"])


@router.post("")
def run_search(face_id: str = Body(..., embed=True),
               match_selection: str | int = Body("auto", embed=True)):
    conn = get_conn()
    try:
        face = conn.execute("SELECT * FROM faces WHERE id = ?", (face_id,)).fetchone()
        if face is None:
            raise HTTPException(404, "face_id not found")
        selection = match_selection
        if isinstance(selection, str) and selection.isdigit():
            selection = int(selection)
        return search_service.run_and_persist(conn, face_id, face["image_path"], selection)
    except search_service.SearchError as e:
        raise HTTPException(422, str(e))
    finally:
        conn.close()


@router.get("/{search_id}")
def get_search(search_id: str):
    conn = get_conn()
    try:
        row = search_service.get_search(conn, search_id)
        if row is None:
            raise HTTPException(404, "search not found")
        import json
        d = dict(row)
        d["raw_response"] = json.loads(d["raw_response"])
        return d
    finally:
        conn.close()
