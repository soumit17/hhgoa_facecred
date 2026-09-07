"""Central paths and settings. The DB path is fixed and documented because the
separate tamper_demo.ipynb notebook opens the exact same file."""
import os
import pathlib

try:
    from dotenv import load_dotenv
    # Load webapp/.env and the repo-root .env if present (root holds the shared SERPAPI_KEY).
    load_dotenv(pathlib.Path(__file__).resolve().parents[2] / ".env", override=False)
    load_dotenv(pathlib.Path(__file__).resolve().parents[3] / ".env", override=False)
except Exception:
    pass

BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1]        # .../webapp/backend
DATA_DIR = BACKEND_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "app.db"                                    # <-- fixed, shared with tamper notebook
SCHEMA_PATH = BACKEND_DIR / "app" / "schema.sql"

SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "").strip()
SEPOLIA_RPC_URL = os.environ.get("SEPOLIA_RPC_URL", "").strip()
WALLET_PRIVATE_KEY = os.environ.get("WALLET_PRIVATE_KEY", "").strip()

GENESIS_PREV_HASH = "0" * 64

DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
