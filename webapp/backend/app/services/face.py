"""Stage 1 — face detection & encoding. Ported from face_blockchain_pipeline.ipynb.

Uses face_recognition (dlib 128-d embedding) when available; otherwise falls back to
an OpenCV Haar Cascade detector + a flattened pixel vector so the pipeline never
hard-fails.
"""
import json
import uuid
from datetime import datetime, timezone

import cv2
import numpy as np

from ..config import UPLOAD_DIR
from .hashing import sha256_bytes, sha256_text

FACE_RECOGNITION_AVAILABLE = True
try:  # pragma: no cover - import guard
    import face_recognition
except Exception:  # ImportError or dlib load failure
    FACE_RECOGNITION_AVAILABLE = False


class FaceError(RuntimeError):
    """Raised when no usable face can be produced from an image."""


def save_upload(raw: bytes, original_name: str) -> str:
    ext = "".join(c for c in (original_name.rsplit(".", 1)[-1] if "." in original_name else "jpg")
                  if c.isalnum()) or "jpg"
    fname = f"{uuid.uuid4().hex}.{ext.lower()}"
    path = UPLOAD_DIR / fname
    path.write_bytes(raw)
    return str(path)


def detect_and_encode(image_path: str) -> dict:
    """Return {bounding_box, encoding (list[float]), encoding_method, image_size}."""
    image = cv2.imread(image_path)
    if image is None:
        raise FaceError(f"Could not read image at '{image_path}'.")
    h, w = image.shape[:2]
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    if FACE_RECOGNITION_AVAILABLE:
        locations = face_recognition.face_locations(rgb)
        if not locations:
            raise FaceError("No face detected. Try a clearer, front-facing photo.")
        encodings = face_recognition.face_encodings(rgb, locations)
        top, right, bottom, left = locations[0]
        return {
            "bounding_box": {"top": top, "right": right, "bottom": bottom, "left": left},
            "encoding": [float(x) for x in np.asarray(encodings[0])],
            "encoding_method": "dlib",
            "image_size": {"width": w, "height": h},
        }

    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)
    if len(faces) == 0:
        raise FaceError("No face detected. Try a clearer, front-facing photo.")
    x, y, fw, fh = faces[0]
    crop = cv2.resize(gray[y:y + fh, x:x + fw], (64, 64))
    return {
        "bounding_box": {"top": int(y), "right": int(x + fw), "bottom": int(y + fh), "left": int(x)},
        "encoding": [float(v) for v in (crop.flatten() / 255.0)],
        "encoding_method": "opencv_fallback",
        "image_size": {"width": w, "height": h},
    }


def persist_face(conn, image_path: str, result: dict) -> dict:
    """Insert a faces row. encoding_hash is sha256 of the exact stored JSON text."""
    face_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()

    with open(image_path, "rb") as f:
        image_hash = sha256_bytes(f.read())

    encoding_vector = json.dumps(result["encoding"])
    encoding_hash = sha256_text(encoding_vector)

    conn.execute(
        """INSERT INTO faces (id, image_path, image_hash, encoding_vector, encoding_hash,
                              encoding_method, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (face_id, image_path, image_hash, encoding_vector, encoding_hash,
         result["encoding_method"], now),
    )
    conn.commit()
    return {
        "face_id": face_id,
        "encoding_method": result["encoding_method"],
        "bounding_box": result["bounding_box"],
        "image_size": result["image_size"],
        "image_hash": image_hash,
        "encoding_hash": encoding_hash,
        "thumbnail_url": f"/uploads/{image_path.rsplit('/', 1)[-1]}",
        "created_at": now,
    }


def encode_and_persist(conn, raw: bytes, original_name: str) -> dict:
    path = save_upload(raw, original_name)
    result = detect_and_encode(path)
    return persist_face(conn, path, result)


def get_face(conn, face_id: str):
    return conn.execute("SELECT * FROM faces WHERE id = ?", (face_id,)).fetchone()
