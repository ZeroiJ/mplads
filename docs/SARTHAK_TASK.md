# SARTHAK'S TASK — MPLADS Backend (step-by-step)

You own the **backend** end-to-end. Below is the exact procedure from your
laptop to a live API. Read `docs/BACKEND_SPEC.md` for the full API spec — this
doc is the "what to do, in order" version.

- Backend = Python **FastAPI** that takes raw CSVs at runtime and serves results.
- The ML model lives on a **Hugging Face Space** (yours: RS). Your backend
  *calls* it — it never loads the model itself.

---

## What you need up front
- Clone this repo: `git clone git@github.com:ZeroiJ/mplads.git`
- A **Hugging Face** account (Space for your RS model + token)
- A **free Python host**: Fly.io or Render (either is fine)
- (Optional) `wrangler` CLI for the Cloudflare cache

---

## Phase 1 — Push your RS model to HF Space  (1–2 hrs)
1. Locate your trained weights on your machine:
   ```
   models/rs/epoch_4.0/
   ```
   Not there? Run `git lfs pull` inside the repo first.
2. On huggingface.co → **New Space** → name `mplads-rs-embed` → SDK = **Docker**.
3. Add files to the Space:
   - `app.py` — two endpoints (copy the file from the group):
     - `POST /predict` → body `{"text": "..."}` → returns a **384-dim vector**
     - `GET /health` → `{"status":"ok"}`
   - your `models/rs/epoch_4.0/` folder
   - `Dockerfile` + `requirements.txt` (`sentence_transformers`, `fastapi`, `uvicorn`)
4. **Restart this space** → it builds. Copy the URL:
   ```
   https://sarthak-mplads-rs-embed.hf.space
   ```
5. **HF token**: Settings → Access Tokens → **Read**. Send it to Zeroij privately
   (the backend needs it as `HF_TOKEN`).
6. **UptimeRobot** → add monitor → URL = your Space `/health`, interval **5 min**.
   This keeps the free Space awake.

**CHECKPOINT:** `curl https://sarthak-mplads-rs-embed.hf.space/health` returns ok.

---

## Phase 2 — Build the FastAPI backend  (3–5 hrs)
```bash
mkdir mplads-backend && cd mplads-backend
python -m venv .venv && source .venv/bin/activate
pip install fastapi uvicorn[standard] python-multipart pandas pydantic httpx python-dotenv
```

In `app.py`, wire in the repo's pipeline package **instead of copying precomputed CSVs**:
```python
import sys
sys.path.insert(0, "/home/zeroij/mplads")        # path where you cloned the repo
from src.mplads import config, engine, aggregate, evidence
```

Implement the endpoints per `docs/BACKEND_SPEC.md`. The complete skeleton is in
that spec's "Step 3 — app.py" block — copy and adapt it. The endpoints:
- `GET /health`
- `POST /api/upload` — accepts the **4 raw CSVs**, runs the pipeline **in memory**
- `GET /api/works` — filter/paginate flagged works
- `GET /api/works/{work_id}` — single work + evidence markdown
- `GET /api/mps` and `GET /api/offenders` — MP rankings
- `POST /api/similar` — needs the model (Phase 3)

Create the env file (never commit):
```
HF_TOKEN=<read token from Phase 1>
HF_SPACE_RS=https://sarthak-mplads-rs-embed.hf.space
```

Test locally:
```bash
uvicorn app:app --host 0.0.0.0 --port 8000
curl localhost:8000/health
curl -X POST localhost:8000/api/upload \
     -F "works_recommended=@Works Recommended.csv" \
     -F "works_sanctioned=@Works Sanctioned.csv" \
     -F "works_completed=@Works Completed.csv" \
     -F "expenditure=@Expenditure on Completed and On-going Works as on Date.csv"
curl "localhost:8000/api/offenders?top=5"
```

**CHECKPOINT:** all smoke-test curls pass (spec Step 9).

---

## Phase 3 — `/api/similar` (the live HF call)  (1–2 hrs)
1. On each upload, embed the **flagged** `work_desc`s by calling your HF Space
   `/predict`, and cache `{work_id: [384 floats]} `in memory (used again by D2
   duplicate detection).
2. Implement:
   ```python
   @app.post("/api/similar")
   async def similar(desc=Body(...), k=5):
       anchors = current_embeddings                 # from the live upload
       emb = await call_hf_space(desc, HF_TOKEN)    # POST your Space /predict
       scores = cosine(emb, anchors)                # your HF call
       return {"desc": desc, "similar": topk(scores, k)}
   ```
3. `call_hf_space` = POST to your Space `/predict` with `HF_TOKEN` in the header,
   with retry + timeout (503 if HF is down).

**CHECKPOINT:** posting a description returns top-k similar works.

---

## Phase 4 — CORS + token-gate + rate limit  (1 hr)
- `CORSMiddleware` with `allow_origins=["*"]` (spec Step 7) so Riya's dashboard can call you.
- Gate `/api/similar` behind a header token + simple rate limit (10 req/min/IP) so randoms don't burn the free HF quota.

---

## Phase 5 — Deploy to a free Python host  (1–2 hrs)
- **Fly.io:** `fly launch` → `fly secrets set HF_TOKEN=... HF_SPACE_RS=...` → `fly deploy`.
- **Render:** push the backend to its own GitHub repo → New Web Service → free tier → add env vars → deploy.

**CHECKPOINT:** public URL `/health` responds from the internet.

---

## Phase 6 — Smoke-test the public API
```bash
curl -s <base>/health
curl -s -X POST <base>/api/upload \
     -F "works_recommended=@Works Recommended.csv" \
     -F "works_sanctioned=@Works Sanctioned.csv" \
     -F "works_completed=@Works Completed.csv" \
     -F "expenditure=@Expenditure on Completed and On-going Works as on Date.csv"
curl -s "<base>/api/works?mp=Chandra&page=1"
curl -s "<base>/api/offenders?top=5"
curl -s -X POST <base>/api/similar -d '{"desc":"concrete road near Magrahat"}'
```
First offender row should be **Chandra Prakash Choudhary** (cumulative 2039 pts).

---

## Phase 7 — Hand off  (30 min)
Send the group:
- The public **base URL**
- The **HF token** (private message, not in a file)
- Confirm **UptimeRobot** is monitoring `/health`
- Confirm which Space is **LS** vs **RS**

---

## Optional — Cloudflare cache (only if you want it)
FastAPI can't run on Cloudflare Workers (JS/TS only). The CF Worker is a thin
**read-only cache** in front of your FastAPI URL: an `src/index.ts` with an
`Env` interface, a `getCsv()` helper, and KV `cache.get`/`cache.put` storing
live-uploaded responses. It's what "fits Cloudflare" — not the backend itself.
Skip it if time is tight; FastAPI exposed directly (with CORS) is fine.

---

## Priority if the deadline is close
1. **Phase 1** (HF Space — takes longest to build)
2. **Phase 2** + **Phase 6** (a working read + upload + offenders API)
3. **Phase 3** `/api/similar` — nice-to-have, add if time permits

**Total estimate: ~1 to 1.5 days of focused work.**