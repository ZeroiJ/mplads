# RIYA'S TASK — MPLADS Frontend (step-by-step)

You own the **frontend**. Below is the exact procedure. The app is simple but
specific: let the judge **upload raw CSVs**, then show the results the backend
computed from them. Built with **React (Vite)**, deployed free on **Cloudflare
Pages**.

Read `docs/BACKEND_SPEC.md` for the API details. This doc is the "what to build,
in order" version.

---

## The whole user flow (this is the UX you build)
```
Landing → Upload page (drag-drop / browse 4 CSVs) → "Analyzing…" spinner
       → Results dashboard (flagged works, filters) → MP leaders → Work detail (dossier)
       → Similarity checker (type a description)
```
The **only** input is the CSV upload. Everything after is read from the backend API.

---

## What you need up front
- Node.js installed
- A GitHub account (to deploy on Cloudflare Pages)
- The backend base URL from Sarthak (the `API` host)

---

## Phase 1 — Scaffold + upload screen  (fresh project)
```bash
npm create vite@latest mplads-frontend -- --template react
cd mplads-frontend && npm install
npm install react-router-dom
```

Build one **"Upload" screen**:
- A big dropzone: drag a file over it, **or** Browse.
- Accept **4 CSV files**: Works Recommended / Sanctioned / Completed / Expenditure.
- Show which of the 4 are still missing (checklist).
- A **"Run Detection"** button that POSTs the 4 files to `POST /api/upload`.

**Code shape** (use this exact call):
```js
const form = new FormData();
form.append("works_recommended", file1);
form.append("works_sanctioned", file2);
form.append("works_completed", file3);
form.append("expenditure", file4);
const res = await fetch(`${API}/api/upload`, { method: "POST", body: form });
```
`API` = the backend base URL (put it in a config file, e.g. `.env`:
`VITE_API_URL=...`).

While it runs, show a spinner + "Analyzing…". The backend returns
`{ works, flagged }` — show those two numbers on completion.

**Demo nicety:** a **"Use sample data"** button that calls upload with the repo's
seeded `data/raw/*.csv`, so the demo works even before a judge drops files.

---

## Phase 2 — Results dashboard (the core)
After upload returns, route to `/results`.

**"Flagged Works" table** (calls `GET /api/works?page=&page_size=50`):

| Column | Source |
|--------|--------|
| Name / work_id | `work_id` |
| MP | `mp_name` |
| State | `mp_state` |
| Description | `work_desc` |
| Amount sanctioned | `sanction_amount` |
| Risk score | `risk_score` (0-100) |
| Fraud type | `fraud_type` |
| Legal route | `legal_route` |

**Filters** above the table (all optional, AND-combined): search box for MP, a
`fraud_type` dropdown, min-risk slider, pagination.

**IMPORTANT safety rule — the red text you must show:** when a row has a high
`risk_score`, the cell shows **"Possible fraud pattern — verification required
by scheme authority."** Never render the word "guilty." This is locked.

---

## Phase 3 — MP leaders
A second view, **"MP Risk Rankings"** via `GET /api/offenders?top=20`:
- Show a ranked list/bar: MP name + `risk_rank`.
- **Render TWO separate numbers as TWO columns:**
  - `cumulative_risk_points` (a sum — can be large)
  - `avg_risk_per_work` (0-100)
  - ⚠️ Never merge these under one "risk score" label.
- You can even auto-open the worst offender's evidence.

---

## Phase 4 — Work detail (evidence dossier)
Clicking a table row → route to `/works/:workId` via `GET /api/works/{work_id}`.
Render:
- The row's fields (amounts, status, flags)
- The `evidence` markdown from the API — render it as a formatted card (add
  `react-markdown`), with the **"Possible legitimate explanation"** and
  **verification checklist** sections visible. That's the human-review story
  that protects you from false-positive criticism.

---

## Phase 5 — Similarity checker (optional, if time)
A search box: type a work description → `POST /api/similar` → show top-k similar
flagged works with similarity scores. Nice-to-have; the backend gates it with a
token/rate-limit.

---

## Phase 6 — Deploy on Cloudflare Pages (free)
1. Push the frontend to its own GitHub repo.
2. Cloudflare Dashboard → **Workers & Pages → Create → Pages** → connect the repo.
3. Build command: `npm run build`, output dir: `dist`.
4. Set env var `VITE_API_URL` = your backend URL in Pages settings →
   Environment variables.
5. Deploy. You get a free `*.pages.dev` URL.

---

## The exact page map (so you don't over-build)
| Route | Screen | API call |
|-------|--------|----------|
| `/` | Upload (drag-drop/browse) | `POST /api/upload` |
| `/results` | Flagged works table + filters | `GET /api/works` |
| `/mp-rankings` | MP leaderboard | `GET /api/offenders` |
| `/works/:id` | Work detail + evidence dossier | `GET /api/works/{id}` |
| `/similarity` | (optional) type-description search | `POST /api/similar` |

**Scope guard:** 5 screens, 4 API endpoints. Don't build auth, don't build a
database, don't build dashboards for pre-recorded data. The app reads **only**
from the fresh upload — that's the "live, not pre-recorded" rule on the frontend
too.

---

## Handoff checklist
- Two screens **mandatory**: **Upload** (with sample-data fallback) and
  **Results table**.
- Show the red "possible pattern / verification required" phrasing on risky rows.
- MP rankings split `cumulative_risk_points` vs `avg_risk_per_work` as separate
  columns.
- Deployed to Cloudflare Pages; `VITE_API_URL` connected to Sarthak's backend URL.