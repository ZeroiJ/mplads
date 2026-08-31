# DEMO GUIDE — What if we don't have a webapp?

The detection pipeline is fully built and produces real outputs. The webapp is a
**nice-to-have layer on top**, not a requirement. Here are two ways to demo the
system today, with zero frontend code.

---

## Option A: TUI (Terminal User Interface)

A colorful, interactive terminal app built with Python's `rich` library. Runs
locally, no internet needed, looks polished in a demo video.

### Setup

```bash
pip install rich
python scripts/tui.py
```

### What you see

```
┌─ MPLADS Fraud Detection System ─────────────────────────┐
│  Lok Sabha + Rajya Sabha • 17,879 works • 3,815 flagged │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  [1] Run Detection Pipeline                             │
│  [2] Browse Flagged Works                               │
│  [3] MP Risk Rankings                                   │
│  [4] Case Dossier Viewer                                │
│  [5] Live Similarity Check                              │
│  [6] Model Stats                                        │
│                                                         │
│  [q] Quit                                               │
└─────────────────────────────────────────────────────────┘
```

### Step-by-step demo flow

**Step 1: Launch**
```bash
python scripts/tui.py
```
Show the menu. Point out: "17,879 works analyzed, 3,815 flagged, 0 hallucinations."

**Step 2: Browse Flagged Works (option 2)**
- Press `2` → shows a colored table of all flagged works
- Filter by MP name, state, fraud type, or minimum risk score
- Table shows: work_id, MP, description (truncated), fraud_type, risk_score, legal_route
- Red rows = high risk, yellow = medium, green = low

**Step 3: MP Risk Rankings (option 3)**
- Press `3` → shows top 20 worst offenders
- Columns: rank, MP name, state, cumulative_risk_points, avg_risk_per_work
- Point out: "cumulative_risk_points is the sum across all their works — not a 0-100 scale"

**Step 4: Case Dossier (option 4)**
- Press `4` → enter a work_id (e.g., `MP18144/2024-2025/135750`)
- Shows the full dossier:
  - **FC1 section**: "Why it looks wrong" — pattern-based narrative (no accusation)
  - **LG1 section**: Legal route — BNS/PC Act/PMLA/RTI, hardcoded, verbatim
  - **Evidence**: Raw data rows from the original source files
  - **Verification checklist**: What an investigator should check

**Step 5: Live Similarity Check (option 5)**
- Press `5` → type a random work description:
  ```
  > Supply of beds and mattresses to primary health centre in rural area
  ```
- Model returns top 5 most similar flagged works with similarity scores
- Show how the model catches re-listed works with slightly different wording

**Step 6: Model Stats (option 6)**
- Shows: validation accuracy (96.3%), test precision@k (0.45), training epochs, model size
- Explain: "96% means the model correctly identifies which descriptions are the same work — not that 96% of flags are fraud"

---

## Option B: Raw Terminal Demo

No TUI needed — just Python scripts and CSV output. Works on any machine with
Python installed.

### Step-by-step demo flow

**Step 1: Run the pipeline**
```bash
python scripts/run_detection.py
```
Terminal shows:
- Loading 17,879 works...
- D1: Isolation Forest anomaly detection... 894 anomalies
- D2: Duplicate detection (MiniLM-L12-v2)... 468 dup-claim leads
- D3: Stalled/zero-disbursal rules... 1,190 stalled, 2,777 zero disbursal
- FC1: Fraud classification... 2,177 statistical_anomaly, 1,170 siphoned_funds, 468 duplicate_claim
- Output: metrics/flags.csv (3,815 flagged), metrics/mp_aggregate.csv, evidence/*.md

**Step 2: Show the outputs**
```bash
# Top 10 riskiest works
head -11 metrics/flags.csv | column -t -s,

# Top 5 worst MPs
head -6 metrics/mp_aggregate.csv | column -t -s,

# Number of dossiers generated
ls evidence/*.md | wc -l
```

**Step 3: Show a specific case**
```bash
cat evidence/MP18144_2024-2025_135750.md
```
Read through the dossier: FC1 narrative, LG1 legal route, evidence rows.

**Step 4: Model discrimination demo**
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

**Step 5: Show architecture**
```bash
# Render the mermaid diagram (optional, or just open in GitHub)
cat architecture/sih26102_mplads_architecture.mermaid
```

---

## Demo Video Script (2-3 minutes)

| Time | What | What to say |
|------|------|-------------|
| 0:00 | Problem | "MPs get 5 crore per year for local development. Some exploit it. This system detects fraud patterns." |
| 0:20 | Pipeline run | Show `run_detection.py` executing. "Processing 17,879 works — 3,815 flagged with specific fraud patterns." |
| 0:50 | Model demo | Show similarity scores. "The model learns which descriptions are the same work re-listed with different words." |
| 1:10 | Dossier | Open one evidence file. "For each flag: why it looks wrong, which law applies, raw evidence." |
| 1:40 | Top offenders | Show MP rankings. "These MPs have the highest cumulative risk across all their works." |
| 2:00 | Architecture | Walk through diagram. "Data → features → anomaly detection + duplicate detection + rules → classification → legal lookup → evidence." |
| 2:30 | Cost / fairness | "$0 infrastructure. Model never accuses anyone — only flags patterns for human review. Legal routes are hardcoded, not generated." |

---

## Why this works for judging

- **"Is it real?"** → Yes, the pipeline runs live and produces real output
- **"Does the ML actually work?"** → Yes, show the model discriminating similar vs different descriptions
- **"Is it fair?"** → Yes, FC1 is pattern-based, LG1 is hardcoded, never "guilty"
- **"What's the model doing?"** → Embedding similarity — comparing text descriptions to find re-listed works
- **"Cost?"** → $0. Model is 470MB, runs on free HuggingFace Spaces

The webapp (when Riya builds it) is a UI layer on top of these same outputs.
The pipeline IS the product.
