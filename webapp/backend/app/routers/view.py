"""The tamper-detection screen's API. Everything here is recomputed live per request."""
from fastapi import APIRouter, HTTPException

from ..db import get_conn
from ..services import verify as verify_service

router = APIRouter(prefix="/api/view", tags=["view"])


@router.get("/records")
def records():
    conn = get_conn()
    try:
        return {"records": verify_service.list_records(conn)}
    finally:
        conn.close()


@router.get("/records/{run_id}")
def record_detail(run_id: str):
    conn = get_conn()
    try:
        return verify_service.verify_run(conn, run_id)
    except KeyError:
        raise HTTPException(404, "run not found")
    finally:
        conn.close()
