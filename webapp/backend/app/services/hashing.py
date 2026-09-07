"""All hashing lives here so the write path (chain.add_block) and the read path
(verify.py) compute hashes identically. Change a formula in exactly one place."""
import hashlib

from ..config import GENESIS_PREV_HASH  # noqa: F401  (re-exported for convenience)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def post_hash(title: str, url: str, source: str) -> str:
    """sha256 of (title + url + source), concatenated in that order."""
    return sha256_text(title + url + source)


def payload_hash(image_hash: str, encoding_hash: str, post_hash_value: str) -> str:
    """sha256(image_hash + encoding_hash + post_hash)."""
    return sha256_text(image_hash + encoding_hash + post_hash_value)


def block_hash(prev_hash: str, payload_hash_value: str) -> str:
    """sha256(prev_hash + payload_hash)."""
    return sha256_text(prev_hash + payload_hash_value)
