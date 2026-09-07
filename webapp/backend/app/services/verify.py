"""Live verification (Section 5 of the build plan).

Nothing here trusts a stored status. Every hash is recomputed from the *current* row
data / file on disk each time this runs. That is what makes the tamper demo work with
no extra step: edit a data column directly in the DB and the very next call here
recomputes a hash that no longer matches what was stored.

Chain cascade: each block's recomputed block_hash is built from the *recomputed*
block_hash of the previous block, so tampering a middle block turns every later block
red too.
"""
import json
import os

from .hashing import block_hash as compute_block_hash
from .hashing import payload_hash as compute_payload_hash
from .hashing import post_hash as compute_post_hash
from .hashing import sha256_bytes, sha256_text
from ..config import GENESIS_PREV_HASH


def _verify_face(face) -> dict:
    if os.path.exists(face["image_path"]):
        with open(face["image_path"], "rb") as f:
            recomputed_image_hash = sha256_bytes(f.read())
        image_ok = recomputed_image_hash == face["image_hash"]
    else:
        recomputed_image_hash = None
        image_ok = False

    recomputed_encoding_hash = sha256_text(face["encoding_vector"])
    encoding_ok = recomputed_encoding_hash == face["encoding_hash"]

    problems = []
    if not image_ok:
        problems.append("source image bytes do not match the stored image hash"
                        if recomputed_image_hash else "source image file is missing from disk")
    if not encoding_ok:
        problems.append("face encoding vector does not match its stored hash")

    return {
        "face_id": face["id"],
        "encoding_method": face["encoding_method"],
        "stored_image_hash": face["image_hash"],
        "recomputed_image_hash": recomputed_image_hash,
        "stored_encoding_hash": face["encoding_hash"],
        "recomputed_encoding_hash": recomputed_encoding_hash,
        "status": "verified" if (image_ok and encoding_ok) else "tampered",
        "problems": problems,
        # current hashes, reused by the block check:
        "_image_hash": recomputed_image_hash or "",
        "_encoding_hash": recomputed_encoding_hash,
    }


def _verify_search(search) -> dict:
    recomputed_post_hash = compute_post_hash(
        search["matched_post_title"], search["matched_post_url"], search["matched_post_source"]
    )
    ok = recomputed_post_hash == search["post_hash"]
    return {
        "search_id": search["id"],
        "matched_post": {
            "title": search["matched_post_title"],
            "url": search["matched_post_url"],
            "source": search["matched_post_source"],
        },
        "stored_post_hash": search["post_hash"],
        "recomputed_post_hash": recomputed_post_hash,
        "status": "verified" if ok else "tampered",
        "problems": [] if ok else ["matched post does not match its stored hash"],
        "_post_hash": recomputed_post_hash,
    }


def compute_chain_state(conn) -> dict:
    """Return {block_id: {...recomputed fields + status...}} for every block, with the
    cascade applied. Also usable standalone for the ledger view."""
    blocks = conn.execute("SELECT * FROM blocks ORDER BY block_index ASC").fetchall()
    faces = {r["id"]: r for r in conn.execute("SELECT * FROM faces").fetchall()}
    searches = {r["id"]: r for r in conn.execute("SELECT * FROM searches").fetchall()}

    state: dict = {}
    prev_recomputed_hash = GENESIS_PREV_HASH
    for b in blocks:
        face = faces.get(b["face_id"])
        search = searches.get(b["search_id"])
        fv = _verify_face(face) if face else {"status": "tampered", "_image_hash": "",
                                              "_encoding_hash": "", "problems": ["face row missing"]}
        sv = _verify_search(search) if search else {"status": "tampered", "_post_hash": "",
                                                    "problems": ["search row missing"]}

        recomputed_payload_hash = compute_payload_hash(
            fv["_image_hash"], fv["_encoding_hash"], sv["_post_hash"]
        )
        recomputed_block_hash = compute_block_hash(prev_recomputed_hash, recomputed_payload_hash)

        payload_ok = recomputed_payload_hash == b["payload_hash"]
        block_hash_ok = recomputed_block_hash == b["block_hash"]
        chain_link_intact = b["prev_hash"] == prev_recomputed_hash

        problems = []
        if not payload_ok:
            problems.append("block payload hash does not match the current face/search hashes")
        if not block_hash_ok:
            problems.append("block hash does not match its recomputed value")
        if not chain_link_intact:
            problems.append("chain link broken: stored prev_hash != previous block's current hash")

        status = "verified" if (payload_ok and block_hash_ok and chain_link_intact) else "tampered"
        state[b["id"]] = {
            "block_id": b["id"],
            "block_index": b["block_index"],
            "face_id": b["face_id"],
            "search_id": b["search_id"],
            "stored_payload_hash": b["payload_hash"],
            "recomputed_payload_hash": recomputed_payload_hash,
            "stored_block_hash": b["block_hash"],
            "recomputed_block_hash": recomputed_block_hash,
            "stored_prev_hash": b["prev_hash"],
            "actual_prev_block_hash": prev_recomputed_hash,
            "chain_link_intact": chain_link_intact,
            "use_real_blockchain": bool(b["use_real_blockchain"]),
            "tx_hash": b["tx_hash"],
            "status": status,
            "problems": problems,
            "_face_view": fv,
            "_search_view": sv,
        }
        prev_recomputed_hash = recomputed_block_hash

    return state


def _strip_private(d: dict) -> dict:
    return {k: v for k, v in d.items() if not k.startswith("_")}


def verify_block(conn, block_id: str) -> dict:
    state = compute_chain_state(conn)
    if block_id not in state:
        raise KeyError(block_id)
    bs = state[block_id]
    fv, sv = bs["_face_view"], bs["_search_view"]
    field_matches = {
        "image_hash": fv.get("recomputed_image_hash") == fv.get("stored_image_hash"),
        "encoding_hash": fv.get("recomputed_encoding_hash") == fv.get("stored_encoding_hash"),
        "post_hash": sv.get("recomputed_post_hash") == sv.get("stored_post_hash"),
        "payload_hash": bs["recomputed_payload_hash"] == bs["stored_payload_hash"],
        "block_hash": bs["recomputed_block_hash"] == bs["stored_block_hash"],
        "chain_link": bs["chain_link_intact"],
    }
    return {
        "block_id": block_id,
        "field_matches": field_matches,
        "valid": all(field_matches.values()),
        "detail": _strip_private(bs),
        "face": _strip_private(fv),
        "search": _strip_private(sv),
    }


def verify_run(conn, run_id: str) -> dict:
    run = conn.execute("SELECT * FROM pipeline_runs WHERE id = ?", (run_id,)).fetchone()
    if run is None:
        raise KeyError(run_id)
    state = compute_chain_state(conn)

    block_state = state.get(run["block_id"]) if run["block_id"] else None
    if block_state:
        face_view = _strip_private(block_state["_face_view"])
        search_view = _strip_private(block_state["_search_view"])
        block_view = _strip_private(block_state)
    else:
        face = conn.execute("SELECT * FROM faces WHERE id = ?", (run["face_id"],)).fetchone()
        search = conn.execute("SELECT * FROM searches WHERE id = ?", (run["search_id"],)).fetchone()
        face_view = _strip_private(_verify_face(face)) if face else None
        search_view = _strip_private(_verify_search(search)) if search else None
        block_view = None

    onchain = {"enabled": False, "tx_hash": None, "status": "not_applicable"}
    if block_view and block_view.get("use_real_blockchain"):
        onchain = {"enabled": True, "tx_hash": block_view.get("tx_hash"), "status": "not_checked"}

    statuses = [v["status"] for v in (face_view, search_view, block_view) if v]
    overall = "verified" if statuses and all(s == "verified" for s in statuses) else "tampered"

    return {
        "run_id": run_id,
        "run_status": run["status"],
        "created_at": run["created_at"],
        "face": face_view,
        "search": search_view,
        "block": block_view,
        "onchain": onchain,
        "overall_status": overall,
    }


def list_records(conn) -> list[dict]:
    runs = conn.execute(
        "SELECT * FROM pipeline_runs ORDER BY created_at ASC"
    ).fetchall()
    state = compute_chain_state(conn)
    out = []
    for run in runs:
        bs = state.get(run["block_id"]) if run["block_id"] else None
        if bs:
            fv, sv = bs["_face_view"], bs["_search_view"]
            statuses = [fv["status"], sv["status"], bs["status"]]
            overall = "verified" if all(s == "verified" for s in statuses) else "tampered"
            matched_title = sv["matched_post"]["title"]
            block_index = bs["block_index"]
            chain_link_intact = bs["chain_link_intact"]
        else:
            overall = "tampered" if run["status"] == "error" else "incomplete"
            matched_title = None
            block_index = None
            chain_link_intact = None
        out.append({
            "run_id": run["id"],
            "created_at": run["created_at"],
            "run_status": run["status"],
            "block_index": block_index,
            "matched_post_title": matched_title,
            "chain_link_intact": chain_link_intact,
            "overall_status": overall,
        })
    return out
