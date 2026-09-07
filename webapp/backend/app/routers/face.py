from fastapi import APIRouter, File, HTTPException, UploadFile

from ..db import get_conn
from ..services import face as face_service

router = APIRouter(prefix="/api/face", tags=["face"])


@router.post("/encode")
async def encode(image: UploadFile = File(...)):
    raw = await image.read()
    if not raw:
        raise HTTPException(400, "Empty upload.")
    conn = get_conn()
    try:
        return face_service.encode_and_persist(conn, raw, image.filename or "upload.jpg")
    except face_service.FaceError as e:
        raise HTTPException(422, str(e))
    finally:
        conn.close()


@router.get("/{face_id}")
def get_face(face_id: str):
    conn = get_conn()
    try:
        row = face_service.get_face(conn, face_id)
        if row is None:
            raise HTTPException(404, "face not found")
        d = dict(row)
        d["thumbnail_url"] = f"/uploads/{d['image_path'].rsplit('/', 1)[-1]}"
        return d
    finally:
        conn.close()
