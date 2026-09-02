"""MPLADS Detection API — FastAPI backend.

Reads the spec at `docs/BACKEND_SPEC.md` and `docs/SARTHAK_TASK.md`.
Only two files are produced: `app.py` and `.env.example`.

The backend never loads the sentence-transformer model itself; it only calls
out to the RS Hugging Face Space for the optional `/api/similar` endpoint.
"""

import asyncio
import datetime
import math
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from fastapi import (
    Body,
    FastAPI,
    File,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

load_dotenv()

# Repo root: the image copies everything into /app (src/, data/, etc.), so if
# we're at /app/app.py the repo root is /app. Locally it's repo root/.. .
REPO_ROOT = Path(os.environ.get("MPLADS_REPO", "")).resolve() if os.environ.get("MPLADS_REPO") else None
if REPO_ROOT is None or not (REPO_ROOT / "src").exists():
    here = Path(__file__).resolve().parent
    REPO_ROOT = here if (here / "src").exists() else Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.mplads import aggregate, config, engine, evidence  # noqa: E402
from src.mplads.duplicates import compute_dup_signals_live  # noqa: E402
from src.mplads.engine import run_engine_on_master  # noqa: E402
from src.mplads.pipeline_from_raw import build_master_from_raw  # noqa: E402

# -----------------------------------------------------------------------------
# Patch the pipeline config to the real repo location on this host.
# -----------------------------------------------------------------------------
config.BASE_DIR = str(REPO_ROOT)
config.DATA_DIR = str(REPO_ROOT / "data")
config.MASTER = str(REPO_ROOT / "data" / "mplads_master_works_v3.csv")
config.RAW_DIR = str(REPO_ROOT / "data" / "raw")
config.METRICS_DIR = str(REPO_ROOT / "metrics")
config.EVIDENCE_DIR = str(REPO_ROOT / "evidence")
config.FLAGS_CSV = str(REPO_ROOT / "metrics" / "flags.csv")
config.MP_AGGREGATE_CSV = str(REPO_ROOT / "metrics" / "mp_aggregate.csv")
config.WORST_OFFENDERS_CSV = str(REPO_ROOT / "metrics" / "worst_offenders.csv")
config.REAL_SWEEP_CSV = str(REPO_ROOT / "metrics" / "real_sweep.csv")
config.PAIRS = str(REPO_ROOT / "data" / "pairs.csv")

# Where the latest uploaded raw CSVs live.
# Render's free tier has a mostly read-only filesystem; /tmp is the safe
# writable location. Override with UPLOAD_DIR for local runs if needed.
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "/tmp/mplads_uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

RAW_FILE_NAMES = {
    "works_recommended": "Works Recommended.csv",
    "works_sanctioned": "Works Sanctioned.csv",
    "works_completed": "Works Completed.csv",
    "expenditure": "Expenditure on Completed and On-going Works as on Date.csv",
}

HF_TOKEN = os.environ.get("HF_TOKEN")
HF_SPACE = os.environ.get("HF_SPACE_LS") or os.environ.get("HF_SPACE_RS")
HF_SPACE_RS = HF_SPACE or os.environ.get("HF_SPACE_RS", "")
API_TOKEN = os.environ.get("API_TOKEN")

# In-memory runtime state.
FLAGS: pd.DataFrame = pd.DataFrame()
MPS: pd.DataFrame = pd.DataFrame()
SOURCE = "none"
EMBEDDINGS: Dict[str, List[float]] = {}

# Simple per-IP rate-limit store for /api/similar.
_REQUEST_LOG: Dict[str, List[datetime.datetime]] = {}


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _raw_paths(raw_dir: str) -> Dict[str, str]:
    return {
        "recommended": os.path.join(raw_dir, "Works Recommended.csv"),
        "sanctioned": os.path.join(raw_dir, "Works Sanctioned.csv"),
        "completed": os.path.join(raw_dir, "Works Completed.csv"),
        "expenditure": os.path.join(raw_dir, "Expenditure on Completed and On-going Works as on Date.csv"),
    }


def _patch_raw_dir(raw_dir: str) -> None:
    """Point the pipeline's evidence module at the uploaded raw CSVs."""
    config.RAW_DIR = raw_dir
    evidence.RAW_FILES = _raw_paths(raw_dir)


def _run_pipeline(raw_dir: str) -> None:
    """Rebuild flags + MP aggregate purely from raw CSVs in ``raw_dir``.

    No precomputed master / real_sweep: the master is assembled from the
    uploaded files, and duplicate detection is computed live via the HF Space
    (with a graceful fallback to zero dup signals if the Space is unavailable).
    """
    global FLAGS, MPS, SOURCE
    _patch_raw_dir(raw_dir)
    master = build_master_from_raw(raw_dir)

    try:
        dup_signals = compute_dup_signals_live(master, _embed_one)
    except Exception:
        # HF Space down / not configured: proceed without dup signals.
        from src.mplads.duplicates import _empty_signals
        dup_signals = _empty_signals(master)

    FLAGS = run_engine_on_master(master, save=False, dup_signals=dup_signals)
    MPS = aggregate.run(FLAGS, save=False)
    SOURCE = "sample" if raw_dir == str(REPO_ROOT / "data" / "raw") else "upload"
    _rebuild_similar_embeddings()


def _clean_records(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Return a JSON-safe list of records with NaN/NA -> None."""
    if df.empty:
        return []
    records = df.where(df.notna(), None).to_dict("records")
    for r in records:
        for k, v in r.items():
            if isinstance(v, float) and math.isnan(v):
                r[k] = None
            elif isinstance(v, np.floating):
                r[k] = float(v)
            elif isinstance(v, np.integer):
                r[k] = int(v)
    return records


def _embed_one(text: str) -> List[float]:
    """Sync embed of a single description via the HF Space (for live D2)."""
    if not HF_TOKEN or not HF_SPACE_RS:
        raise RuntimeError("HF not configured")
    resp = httpx.post(
        f"{HF_SPACE_RS}/predict",
        json={"text": str(text)},
        headers={"Authorization": f"Bearer {HF_TOKEN}"},
        timeout=60.0,
    )
    resp.raise_for_status()
    return resp.json()


def _rebuild_similar_embeddings() -> None:
    """Populate EMBEDDINGS for /api/similar over the current upload.

    If HF is not configured or the space is unreachable, the cache stays empty
    and /api/similar will return a 503. Upload still succeeds.
    """
    global EMBEDDINGS
    EMBEDDINGS = {}
    if not HF_TOKEN or not HF_SPACE_RS:
        return
    if "is_flagged" not in FLAGS.columns:
        return

    flagged = FLAGS[FLAGS["is_flagged"]].copy()
    flagged = flagged[flagged["work_desc"].notna()]
    flagged = flagged[flagged["work_desc"].astype(str).str.strip() != ""]
    # Limit to the top 200 risk works so a free HF Space isn't hammered.
    flagged = flagged.sort_values("risk_score", ascending=False).head(200)

    client = httpx.Client(timeout=60.0)
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    try:
        for _, row in flagged.iterrows():
            wid = str(row["work_id"])
            text = str(row["work_desc"])
            try:
                resp = client.post(
                    f"{HF_SPACE_RS}/predict",
                    json={"text": text},
                    headers=headers,
                )
                resp.raise_for_status()
                EMBEDDINGS[wid] = resp.json()
            except Exception:
                # Stop on first failure to avoid burning quota on a broken space.
                break
    finally:
        client.close()


async def _call_hf_space(text: str) -> List[float]:
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    last_error = None
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{HF_SPACE_RS}/predict",
                    json={"text": text},
                    headers=headers,
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            last_error = exc
            await asyncio.sleep(1.0 * (attempt + 1))
    raise HTTPException(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        f"HF Space unavailable: {last_error}",
    )


def _check_rate_limit(client_host: str) -> bool:
    now = datetime.datetime.now(datetime.timezone.utc)
    window = [t for t in _REQUEST_LOG.get(client_host, []) if (now - t).total_seconds() < 60]
    window.append(now)
    _REQUEST_LOG[client_host] = window
    return len(window) <= 10


# -----------------------------------------------------------------------------
# FastAPI app
# -----------------------------------------------------------------------------
@asynccontextmanager
async def _lifespan(app: FastAPI):
    # Seed the in-memory state with the repo's bundled raw CSVs so the API is
    # usable before any upload (source="sample"). If the sample data is not
    # present (e.g. Render Docker image built from a repo where data/raw is
    # gitignored), start empty and wait for the first upload.
    sample_raw = REPO_ROOT / "data" / "raw"
    if sample_raw.exists() and any(sample_raw.iterdir()):
        _run_pipeline(str(sample_raw))
    yield


app = FastAPI(
    title="MPLADS Detection API",
    version="1.0",
    lifespan=_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "name": "MPLADS Detection API",
        "version": "1.0",
        "endpoints": [
            "GET /health",
            "POST /api/upload",
            "GET /api/works",
            "GET /api/works/{work_id}",
            "GET /api/mps",
            "GET /api/offenders",
            "POST /api/similar",
            "GET /api/similar",
        ],
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "mplads-backend",
        "works": len(FLAGS),
        "source": SOURCE,
    }


@app.post("/api/upload")
async def upload(
    works_recommended: UploadFile = File(...),
    works_sanctioned: UploadFile = File(...),
    works_completed: UploadFile = File(...),
    expenditure: UploadFile = File(...),
):
    files = [
        (works_recommended, "Works Recommended.csv"),
        (works_sanctioned, "Works Sanctioned.csv"),
        (works_completed, "Works Completed.csv"),
        (expenditure, "Expenditure on Completed and On-going Works as on Date.csv"),
    ]
    for up, name in files:
        dest = UPLOAD_DIR / name
        with open(dest, "wb") as f:
            f.write(await up.read())

    _run_pipeline(str(UPLOAD_DIR))
    flagged = int(FLAGS["is_flagged"].sum()) if len(FLAGS) else 0
    return {
        "status": "ok",
        "works": len(FLAGS),
        "flagged": flagged,
        "detected_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


@app.get("/api/works")
def works(
    mp: str = "",
    state: str = "",
    fraud_type: str = "",
    min_risk: float = Query(0.0, ge=0.0, le=100.0),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
):
    if FLAGS.empty:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "No data uploaded yet")

    df = FLAGS[FLAGS["is_flagged"]].copy()
    if mp:
        df = df[df["mp_name"].astype(str).str.contains(mp, case=False, na=False)]
    if state:
        df = df[df["state"].astype(str).str.contains(state, case=False, na=False)]
    if fraud_type:
        df = df[df["fraud_type"] == fraud_type]
    df = df[df["risk_score"] >= min_risk]
    df = df.sort_values("risk_score", ascending=False)
    total = len(df)
    start = (page - 1) * page_size
    rows = df.iloc[start : start + page_size]
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "results": _clean_records(rows),
    }


@app.get("/api/works/{work_id:path}")
def work_detail(work_id: str):
    if FLAGS.empty:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "No data uploaded yet")
    row = FLAGS[FLAGS["work_id"] == work_id]
    if row.empty:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "work_id not found")

    data = _clean_records(row).pop()
    raw_paths = _raw_paths(config.RAW_DIR)
    rows = {src: evidence._find_row(path, work_id) for src, path in raw_paths.items()}
    data["evidence"] = evidence._template(row.iloc[0], rows, row.iloc[0].get("reasons", ""))
    return data


@app.get("/api/mps")
def list_mps():
    if MPS.empty:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "No data uploaded yet")
    rows = MPS.sort_values("cumulative_risk_points", ascending=False)
    return {"total": len(MPS), "mps": _clean_records(rows)}


@app.get("/api/offenders")
def offenders(top: int = Query(20, ge=1)):
    if MPS.empty:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "No data uploaded yet")
    rows = MPS.sort_values("cumulative_risk_points", ascending=False).head(top)
    return {"mps": _clean_records(rows)}


@app.post("/api/similar")
async def similar_post(
    request: Request,
    desc: str = Body(...),
    k: int = Body(5),
    x_api_token: Optional[str] = Header(None, alias="X-API-Token"),
):
    return await _similar(request, desc, k, x_api_token)


@app.get("/api/similar")
async def similar_get(
    request: Request,
    desc: str = Query(...),
    k: int = Query(5, ge=1, le=50),
    x_api_token: Optional[str] = Header(None, alias="X-API-Token"),
):
    return await _similar(request, desc, k, x_api_token)


async def _similar(request: Request, desc: str, k: int, x_api_token: Optional[str]):
    # Optional token gate (only enforced if API_TOKEN is set in the env).
    if API_TOKEN and x_api_token != API_TOKEN:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing X-API-Token")

    client_host = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_host):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Rate limit: 10 req/min/IP")

    if not EMBEDDINGS or not HF_TOKEN or not HF_SPACE_RS:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Similarity service unavailable: no HF Space configured or no embeddings cached",
        )

    emb = await _call_hf_space(desc)
    emb_arr = np.array(emb, dtype=float)
    if emb_arr.ndim == 0 or len(emb_arr) == 0:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Invalid embedding from HF Space")

    ids = list(EMBEDDINGS.keys())
    anchors = np.array([EMBEDDINGS[wid] for wid in ids], dtype=float)
    norm = np.linalg.norm(anchors, axis=1) * np.linalg.norm(emb_arr)
    scores = np.where(norm > 0, np.dot(anchors, emb_arr) / norm, 0.0)
    top_idx = np.argsort(scores)[::-1][:k]
    similar = []
    for idx in top_idx:
        wid = ids[idx]
        work = FLAGS[FLAGS["work_id"] == wid]
        similar.append(
            {
                "work_id": wid,
                "work_desc": str(work.iloc[0]["work_desc"]) if not work.empty else "",
                "score": round(float(scores[idx]), 4),
            }
        )
    return {"desc": desc, "similar": similar}
