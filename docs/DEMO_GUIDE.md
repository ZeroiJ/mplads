# DEMO GUIDE — What if we don't have a webapp?

The detection pipeline is fully built and produces real outputs. The webapp is a
**nice-to-have layer on top**, not a requirement. Here are two ways to demo the
system today, with zero frontend code.

---

## Option A: TUI (Terminal User Interface)

A colorful, interactive terminal app built with Python's `rich` library. Takes
**raw CSVs as input**, runs the full detection pipeline live, and shows results.
No internet needed, looks polished in a demo video.

### Setup

```bash
pip install rich
python scripts/tui.py
```

### How it works

The TUI reads the same raw CSVs that the pipeline uses:
- `data/raw/Works_Recommended.csv`
- `data/raw/Works_Sanctioned.csv`
- `data/raw/Works_Completed.csv`
- `data/raw/Expenditure.csv`
- `data/raw/Lok_Sabha_alloc_limit.csv`

It runs the **full detection engine** in memory (cleaning → features → D1/D2/D3 →
FC1 → LG1 → evidence) and displays results interactively. No precomputed files
needed — it processes raw data from scratch.

### What you see

```
┌─ MPLADS Fraud Detection System ─────────────────────────┐
│  Loading raw data from data/raw/...                      │
│  17,879 works loaded from 5 CSV files                    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  [1] Run Detection Pipeline (live on raw data)          │
│  [2] Browse Flagged Works                               │
│  [3] MP Risk Rankings                                   │
│  [4] Case Dossier Viewer                                │
│  [5] Live Similarity Check                              │
│  [6] Load Different Data Directory                      │
│  [7] Model Stats                                        │
│                                                         │
│  [q] Quit                                               │
└─────────────────────────────────────────────────────────┘
```

### Step-by-step demo flow

**Step 1: Launch and load raw data**
```bash
python scripts/tui.py
# or with a custom data dir:
python scripts/tui.py --data-dir /path/to/raw/csvs
```
Show the menu. Point out: "Loading raw CSVs from data/raw/ — 17,879 works across 5 files."

**Step 2: Run Detection Pipeline (option 1) — the money shot**
- Press `1` → watch the pipeline execute live with progress bars:
  ```
  [1/6] Cleaning + schema normalization...     ✓ 17,879 works
  [2/6] Feature engineering...                 ✓ 17,879 features
  [3/6] D1: Isolation Forest anomaly detection ✓ 894 anomalies
  [4/6] D2: Duplicate detection (embeddings)   ✓ 468 dup-claim leads
  [5/6] D3: Stalled/zero-disbursal rules       ✓ 1,190 stalled, 2,777 zero
  [6/6] FC1 + LG1 classification               ✓ 3,815 flagged
  ```
- "Processing complete. 3,815 suspicious patterns found out of 17,879 works."
- This is the **live demo moment** — the pipeline runs in front of the judge.

**Step 3: Browse Flagged Works (option 2)**
- Press `2` → shows a colored table of all flagged works
- Filter by MP name, state, fraud type, or minimum risk score
- Table shows: work_id, MP, description (truncated), fraud_type, risk_score, legal_route
- Red rows = high risk, yellow = medium, green = low

**Step 4: MP Risk Rankings (option 3)**
- Press `3` → shows top 20 worst offenders
- Columns: rank, MP name, state, cumulative_risk_points, avg_risk_per_work
- Point out: "cumulative_risk_points is the sum across all their works — not a 0-100 scale"

**Step 5: Case Dossier (option 4)**
- Press `4` → enter a work_id (e.g., `MP18144/2024-2025/135750`)
- Shows the full dossier:
  - **FC1 section**: "Why it looks wrong" — pattern-based narrative (no accusation)
  - **LG1 section**: Legal route — BNS/PC Act/PMLA/RTI, hardcoded, verbatim
  - **Evidence**: Raw data rows from the original source files
  - **Verification checklist**: What an investigator should check

**Step 6: Live Similarity Check (option 5)**
- Press `5` → type a random work description:
  ```
  > Supply of beds and mattresses to primary health centre in rural area
  ```
- Model returns top 5 most similar flagged works with similarity scores
- Show how the model catches re-listed works with slightly different wording

**Step 7: Load Different Data (option 6)**
- Press `6` → enter a path to a different data directory
- Useful if you want to demo with Rajya Sabha data (Sarthak's) or a subset

**Step 8: Model Stats (option 7)**
- Shows: validation accuracy (96.3%), test precision@k (0.45), training epochs, model size
- Explain: "96% means the model correctly identifies which descriptions are the same work — not that 96% of flags are fraud"

---

## Option B: Raw Terminal Demo

No TUI needed — just Python scripts and CSV output. Takes raw CSVs as input,
runs the pipeline, shows results. Works on any machine with Python installed.

### Step-by-step demo flow

**Step 1: Show the raw data**
```bash
# Show what we're feeding the system
ls data/raw/
wc -l data/raw/*.csv
```
"Here are the raw CSVs — works recommended, sanctioned, completed, expenditure, allocation limits."

**Step 2: Run the pipeline on raw data**
```bash
python scripts/run_detection.py
```
Terminal shows:
```
Loading raw data from data/raw/...
  Works_Recommended.csv:  17,879 rows
  Works_Sanctioned.csv:   14,203 rows
  Works_Completed.csv:    12,891 rows
  Expenditure.csv:        17,879 rows
  Lok_Sabha_alloc_limit:   543 MPs

Cleaning + feature engineering...     ✓ 17,879 works
D1: Isolation Forest anomaly detection... 894 anomalies
D2: Duplicate detection (MiniLM-L12-v2)... 468 dup-claim leads
D3: Stalled/zero-disbursal rules... 1,190 stalled, 2,777 zero disbursal
FC1: Fraud classification... 2,177 statistical_anomaly, 1,170 siphoned_funds, 468 duplicate_claim
LG1: Legal route annotation... 3,815 routes assigned

Output: metrics/flags.csv (3,815 flagged), metrics/mp_aggregate.csv, evidence/*.md
```

**Step 3: Show the outputs**
```bash
# Top 10 riskiest works
head -11 metrics/flags.csv | column -t -s,

# Top 5 worst MPs
head -6 metrics/mp_aggregate.csv | column -t -s,

# Number of dossiers generated
ls evidence/*.md | wc -l
```

**Step 4: Show a specific case**
```bash
cat evidence/MP18144_2024-2025_135750.md
```
Read through the dossier: FC1 narrative, LG1 legal route, evidence rows.

**Step 5: Model discrimination demo**
```python
python3 -c "
from sentence_transformers import SentenceTransformer
import numpy as np

m = SentenceTransformer('models/best/epoch_4.0')

# Similar works (same thing, different words)
a = m.encode('Construction of concrete road from Magrahat')
b = m.encode('Construction of cement road from Magrahat')
sim = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
print(f'Similar pair: {sim:.3f} (should be ~0.95)')

# Different works
c = m.encode('Supply of hospital beds to PHC')
sim2 = np.dot(a, c) / (np.linalg.norm(a) * np.linalg.norm(c))
print(f'Different pair: {sim2:.3f} (should be ~0.2)')

# A resubmitted work (catches fraud)
d = m.encode('Repair and renovation of road from Magrahat station to ITI')
sim3 = np.dot(a, d) / (np.linalg.norm(a) * np.linalg.norm(d))
print(f'Resubmitted work: {sim3:.3f} (should be ~0.8, flagged as duplicate)')
"
```

**Step 6: Show architecture**
```bash
cat architecture/sih26102_mplads_architecture.mermaid
```

---

## Demo Video Script (2-3 minutes)

| Time | What | What to say |
|------|------|-------------|
| 0:00 | Problem | "MPs get 5 crore per year for local development. Some exploit it. This system detects fraud patterns." |
| 0:15 | Raw data | Show `data/raw/` — "These are the raw CSVs from mplads.gov.in. 17,879 works across 5 files." |
| 0:30 | Pipeline run | Show `run_detection.py` executing with progress bars. "Processing raw data live — cleaning, features, anomaly detection, duplicate detection, classification." |
| 1:00 | Results | "3,815 suspicious patterns found. Each classified with a fraud type and matched to a specific law." |
| 1:20 | Model demo | Show similarity scores. "The model learns which descriptions are the same work re-listed with different words." |
| 1:40 | Dossier | Open one evidence file. "For each flag: why it looks wrong, which law applies, raw evidence." |
| 2:00 | Top offenders | Show MP rankings. "These MPs have the highest cumulative risk across all their works." |
| 2:20 | Architecture | Walk through diagram. "Raw data → features → detection → classification → legal → evidence → dashboard." |
| 2:40 | Cost / fairness | "$0 infrastructure. Model never accuses anyone — only flags patterns for human review. Legal routes are hardcoded, not generated." |

---

## Why this works for judging

- **"Is it real?"** → Yes, the pipeline runs live and produces real output
- **"Does the ML actually work?"** → Yes, show the model discriminating similar vs different descriptions
- **"Is it fair?"** → Yes, FC1 is pattern-based, LG1 is hardcoded, never "guilty"
- **"What's the model doing?"** → Embedding similarity — comparing text descriptions to find re-listed works
- **"Cost?"** → $0. Model is 470MB, runs on free HuggingFace Spaces

The webapp (when Riya builds it) is a UI layer on top of these same outputs.
The pipeline IS the product.
