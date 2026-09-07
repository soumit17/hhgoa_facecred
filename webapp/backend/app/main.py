import pathlib

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import SERPAPI_KEY, UPLOAD_DIR
from .db import init_db
from .routers import chain, face, pipeline, search, view

app = FastAPI(title="Face ID & Blockchain Verification API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # dev only
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup():
    init_db()


@app.get("/api/health")
def health():
    return {"ok": True, "serpapi_key_set": bool(SERPAPI_KEY)}


app.include_router(face.router)
app.include_router(search.router)
app.include_router(chain.router)
app.include_router(pipeline.router)
app.include_router(view.router)

app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

# Serve the built frontend if it exists (production / single-command mode).
_dist = pathlib.Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _dist.is_dir():
    app.mount("/assets", StaticFiles(directory=str(_dist / "assets")), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        candidate = _dist / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_dist / "index.html")  # client-side routing fallback
