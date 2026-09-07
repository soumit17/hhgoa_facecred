from fastapi import APIRouter, Body, HTTPException

from ..db import get_conn
from ..services import chain as chain_service
from ..services import verify as verify_service

router = APIRouter(prefix="/api/chain", tags=["chain"])


@router.post("/add")
def add(face_id: str = Body(..., embed=True),
        search_id: str = Body(..., embed=True),
        match_index: int | None = Body(None, embed=True),
        use_real_blockchain: bool = Body(False, embed=True)):
    conn = get_conn()
    try:
        return chain_service.add_block(conn, face_id, search_id, match_index, use_real_blockchain)
    except chain_service.ChainError as e:
        raise HTTPException(422, str(e))
    finally:
        conn.close()


@router.get("")
def list_chain(limit: int = 100, offset: int = 0):
    conn = get_conn()
    try:
        return {"blocks": chain_service.get_chain(conn, limit, offset)}
    finally:
        conn.close()


@router.post("/verify/{block_id}")
def verify(block_id: str):
    conn = get_conn()
    try:
        return verify_service.verify_block(conn, block_id)
    except KeyError:
        raise HTTPException(404, "block not found")
    finally:
        conn.close()
