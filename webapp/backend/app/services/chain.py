"""Stage 3 — blockchain add. The chain IS the `blocks` table: an append-only table
where each row's block_hash depends on the previous row's block_hash.

Optionally also anchors the block_hash on the Ethereum Sepolia testnet as a
zero-value self-transaction carrying block_hash in the data field (no smart contract).
"""
import json
import uuid
from datetime import datetime, timezone

from ..config import GENESIS_PREV_HASH, SEPOLIA_RPC_URL, WALLET_PRIVATE_KEY
from .hashing import block_hash as compute_block_hash
from .hashing import payload_hash as compute_payload_hash
from .hashing import post_hash


class ChainError(RuntimeError):
    pass


def _last_block(conn):
    return conn.execute(
        "SELECT * FROM blocks ORDER BY block_index DESC LIMIT 1"
    ).fetchone()


def _anchor_on_sepolia(block_hash_hex: str) -> dict:
    if not (SEPOLIA_RPC_URL and WALLET_PRIVATE_KEY):
        raise ChainError("use_real_blockchain=true but SEPOLIA_RPC_URL / WALLET_PRIVATE_KEY are not set.")
    from web3 import Web3

    w3 = Web3(Web3.HTTPProvider(SEPOLIA_RPC_URL))
    if not w3.is_connected():
        raise ChainError("Could not connect to the Sepolia RPC URL.")
    account = w3.eth.account.from_key(WALLET_PRIVATE_KEY)
    tx = {
        "nonce": w3.eth.get_transaction_count(account.address),
        "to": account.address,
        "value": 0,
        "gas": 30000,
        "gasPrice": w3.eth.gas_price,
        "data": "0x" + block_hash_hex,
        "chainId": 11155111,
    }
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    return {
        "tx_hash": tx_hash.hex(),
        "etherscan_url": f"https://sepolia.etherscan.io/tx/{tx_hash.hex()}",
    }


def add_block(conn, face_id: str, search_id: str, match_index=None,
              use_real_blockchain: bool = False) -> dict:
    face = conn.execute("SELECT * FROM faces WHERE id = ?", (face_id,)).fetchone()
    search = conn.execute("SELECT * FROM searches WHERE id = ?", (search_id,)).fetchone()
    if face is None or search is None:
        raise ChainError("face_id or search_id not found.")

    # Optional: re-pick the matched post from the stored raw response and rewrite the
    # searches row so it stays the single source of truth for verification.
    if match_index is not None:
        raw = json.loads(search["raw_response"])
        results = (raw.get("image_results") or raw.get("inline_images")
                   or raw.get("visual_matches") or [])
        if not 0 <= match_index < len(results):
            raise ChainError(f"match_index {match_index} out of range.")
        m = results[match_index]
        title = m.get("title") or "(no title)"
        url = m.get("link") or m.get("source") or ""
        source = m.get("source") or m.get("displayed_link") or ""
        ph = post_hash(title, url, source)
        conn.execute(
            """UPDATE searches SET matched_post_title = ?, matched_post_url = ?,
                   matched_post_source = ?, post_hash = ? WHERE id = ?""",
            (title, url, source, ph, search_id),
        )
        conn.commit()
        search = conn.execute("SELECT * FROM searches WHERE id = ?", (search_id,)).fetchone()

    image_hash = face["image_hash"]
    encoding_hash = face["encoding_hash"]
    ph = search["post_hash"]

    payload = {"image_hash": image_hash, "encoding_hash": encoding_hash, "post_hash": ph}
    payload_hash = compute_payload_hash(image_hash, encoding_hash, ph)

    prev = _last_block(conn)
    prev_hash = prev["block_hash"] if prev else GENESIS_PREV_HASH
    block_index = (prev["block_index"] + 1) if prev else 0
    block_hash = compute_block_hash(prev_hash, payload_hash)

    tx_hash = None
    onchain = {}
    if use_real_blockchain:
        onchain = _anchor_on_sepolia(block_hash)
        tx_hash = onchain["tx_hash"]

    block_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO blocks (id, block_index, face_id, search_id, payload, payload_hash,
               prev_hash, block_hash, use_real_blockchain, tx_hash, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (block_id, block_index, face_id, search_id, json.dumps(payload), payload_hash,
         prev_hash, block_hash, 1 if use_real_blockchain else 0, tx_hash, now),
    )
    conn.commit()
    return {
        "block_id": block_id,
        "block_index": block_index,
        "payload": payload,
        "payload_hash": payload_hash,
        "prev_hash": prev_hash,
        "block_hash": block_hash,
        "use_real_blockchain": use_real_blockchain,
        "tx_hash": tx_hash,
        "etherscan_url": onchain.get("etherscan_url"),
        "created_at": now,
    }


def get_chain(conn, limit: int = 100, offset: int = 0) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM blocks ORDER BY block_index ASC LIMIT ? OFFSET ?", (limit, offset)
    ).fetchall()
    return [dict(r) for r in rows]
