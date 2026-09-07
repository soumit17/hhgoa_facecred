"""Stage 2 — web / social reverse-image search. Ported from face_blockchain_pipeline.ipynb.

Anonymously host the image (uguu.se -> tmpfiles.org -> catbox.moe) to get a public URL,
then run a live SerpApi search (google_reverse_image, falling back to google_lens).
Real search every run — never hardcoded. The full raw response is stored so the UI can
replay a run without burning SerpApi's 250/month quota.
"""
import json
import uuid
from datetime import datetime, timezone

import requests

from ..config import SERPAPI_KEY
from .hashing import post_hash

SOCIAL_DOMAINS = (
    "instagram.com", "twitter.com", "x.com", "facebook.com", "linkedin.com",
    "tiktok.com", "reddit.com", "threads.net", "youtube.com", "commons.wikimedia.org",
    "en.wikipedia.org",
)


class SearchError(RuntimeError):
    """Raised when the image cannot be hosted or the search returns nothing."""


# ---- anonymous image hosting -------------------------------------------------
def _upload_uguu(path, filename):
    with open(path, "rb") as f:
        r = requests.post("https://uguu.se/upload.php",
                          files={"files[]": (filename, f, "application/octet-stream")}, timeout=60)
    r.raise_for_status()
    return r.json()["files"][0]["url"]


def _upload_tmpfiles(path, filename):
    with open(path, "rb") as f:
        r = requests.post("https://tmpfiles.org/api/v1/upload",
                          files={"file": (filename, f, "application/octet-stream")}, timeout=60)
    r.raise_for_status()
    page_url = r.json()["data"]["url"]
    return page_url.replace("tmpfiles.org/", "tmpfiles.org/dl/", 1)


def _upload_catbox(path, filename):
    with open(path, "rb") as f:
        r = requests.post("https://catbox.moe/user/api.php",
                          data={"reqtype": "fileupload"},
                          files={"fileToUpload": (filename, f, "application/octet-stream")}, timeout=60)
    r.raise_for_status()
    url = r.text.strip()
    if not url.startswith("http"):
        raise RuntimeError(f"catbox response: {url!r}")
    return url


_IMAGE_HOSTS = [("uguu.se", _upload_uguu), ("tmpfiles.org", _upload_tmpfiles),
                ("catbox.moe", _upload_catbox)]


def upload_image_get_public_url(image_path: str) -> str:
    filename = image_path.rsplit("/", 1)[-1]
    errors = []
    for name, fn in _IMAGE_HOSTS:
        try:
            return fn(image_path, filename)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{name}: {e}")
    raise SearchError("All anonymous image hosts failed:\n  " + "\n  ".join(errors))


# ---- SerpApi --------------------------------------------------------------------
def _normalise(data: dict) -> list[dict]:
    raw = (data.get("image_results") or data.get("inline_images")
           or data.get("visual_matches") or [])
    out = []
    for r in raw:
        out.append({
            "title": r.get("title") or "(no title)",
            "url": r.get("link") or r.get("source") or "",
            "source": r.get("source") or r.get("displayed_link") or "",
            "thumbnail": r.get("thumbnail"),
        })
    return out


def reverse_image_search(image_url: str) -> tuple[list[dict], dict]:
    if not SERPAPI_KEY:
        raise SearchError("SERPAPI_KEY is not set on the backend (add it to .env).")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                             "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    attempts = [
        {"engine": "google_reverse_image", "image_url": image_url, "api_key": SERPAPI_KEY},
        {"engine": "google_lens", "url": image_url, "api_key": SERPAPI_KEY},
    ]
    last = {}
    for params in attempts:
        resp = requests.get("https://serpapi.com/search", params=params, headers=headers, timeout=60)
        if resp.status_code != 200:
            last = {"error": f"HTTP {resp.status_code} from {params['engine']}"}
            continue
        data = resp.json()
        last = data
        if data.get("error"):
            continue
        matches = _normalise(data)
        if matches:
            data["_engine_used"] = params["engine"]
            return matches, data
    raise SearchError(last.get("error") or "The search API returned no matches for this image.")


def choose_match(matches: list[dict], selection) -> tuple[int, str]:
    """selection: 'auto', or an int index. Returns (index, human-readable reason)."""
    if not matches:
        raise SearchError("No matches to choose from.")
    if isinstance(selection, int):
        if not 0 <= selection < len(matches):
            raise SearchError(f"match index {selection} out of range (0..{len(matches) - 1}).")
        return selection, f"manual selection: index {selection}"
    for i, m in enumerate(matches):
        link = (m.get("url") or "").lower()
        if any(d in link for d in SOCIAL_DOMAINS):
            return i, f"auto: first known social/reference domain ({link})"
    return 0, "auto: top-ranked result (no social/reference domain in results)"


# ---- persistence --------------------------------------------------------------
def run_and_persist(conn, face_id: str, image_path: str, selection="auto") -> dict:
    query_url = upload_image_get_public_url(image_path)
    matches, raw = reverse_image_search(query_url)
    idx, reason = choose_match(matches, selection)
    chosen = matches[idx]

    search_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    ph = post_hash(chosen["title"], chosen["url"], chosen["source"])
    conn.execute(
        """INSERT INTO searches (id, face_id, query_image_url, raw_response,
               matched_post_title, matched_post_url, matched_post_source, post_hash, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (search_id, face_id, query_url, json.dumps(raw), chosen["title"], chosen["url"],
         chosen["source"], ph, now),
    )
    conn.commit()
    return {
        "search_id": search_id,
        "query_url": query_url,
        "engine_used": raw.get("_engine_used"),
        "matches": matches,
        "selected_index": idx,
        "selection_reason": reason,
        "matched_post": chosen,
        "post_hash": ph,
        "created_at": now,
    }


def get_search(conn, search_id: str):
    return conn.execute("SELECT * FROM searches WHERE id = ?", (search_id,)).fetchone()
