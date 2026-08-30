# MPLADS Fraud-Detection System

**SIH 2026 · Smart India Hackathon** — Real-time fraud detection for the **Members of Parliament Local Area Development Scheme (MPLADS)** using public Government of India data.

Built for **government enforcement / investigation agencies** (ED, CBI, CVC, state ACBs) — not a public dashboard. Output is an **investigative evidence trail** that flags suspicious works, states what was done, and points to the applicable legal route.

---

## The Pipeline

```mermaid
flowchart TD
    subgraph RAWLS["Raw - Lok Sabha (have)"]
        L1[Works_Recommended.csv]
        L2[Works_Sanctioned.csv]
        L3[Works_Completed.csv]
        L4[Expenditure.csv]
        L5[Lok_Sabha_alloc_limit.csv - 543 MPs]
        L6[Amount_consented_for_Calamity.csv - 13 rows, 11 MPs]
    end

    subgraph RAWRS["Raw - Rajya Sabha (to pull)"]
        RS1[Works_Recommended.csv - RS]
        RS2[Works_Sanctioned.csv - RS]
        RS3[Works_Completed.csv - RS]
        RS4[Expenditure.csv - RS]
        RS5[Rajya_Sabha_alloc_limit.csv]
    end

    subgraph CLEAN["Cleaning Layer"]
        C1[Strip BOM + ALL whitespace incl embedded tabs, before any ID parsing]
        C2[Split Work field: WS-ID left of first dash, Work TITLE right of it - do NOT call this Category]
        C3[True Work Category stays its own column - Normal/Others, Trust and Society, Repair and Renovation]
        C4[Parse work_id into mp_no / fy / work_no]
        C5{ID parses?}
        C5A[Valid WS-ID - normal path]
        C5B[NA- or unparseable - kept, flagged unparseable_id=true, not dropped]
    end

    subgraph MERGE["Master Build - both chambers, same logic"]
        M1[Union 4 stage tables by work_id: is_recommended/is_sanctioned/is_completed/has_expenditure]
        M2[Backfill mp_name/state/constituency from Expenditure - never backfill work_category from Expenditure, it has no true category column]
        M3[LEFT JOIN full alloc_limit roster - all 543 LS + all RS MPs, even zero-works MPs, so denominators are correct]
        M4[Join calamity_consent]
        M5[Concatenate LS master + RS master]
    end

    subgraph MASTEROUT["mplads_master_works_ALL.csv"]
        O1[Every allocation-roster MP present, even with zero works]
        O2[unparseable_id flag preserved, not silently dropped]
        O3[work_title vs work_category kept semantically separate]
    end

    subgraph AGG["MP-Level Aggregate Table"]
        A1[Per MP: works count, sanctioned vs disbursed, avg delay, overrun count, spend vs alloc_limit pct]
        A2[Worst-offenders ranking - the MP-risk view]
    end

    subgraph FEAT["Feature Engineering - per work"]
        F1[sanctioned - recommended delta]
        F2[disbursed / sanctioned ratio]
        F3[vendor count per work]
        F4[days between stage transitions]
    end

    subgraph DETECT["Detection Engine"]
        D0[Semantic embeddings - paraphrase-multilingual-MiniLM-L12-v2]
        D1[Anomaly scores - Isolation Forest]
        D2[Duplicate fuzzy-match: MP + category + amount + description]
        D3[Overrun / delay rule flags]
    end

    subgraph CLASSIFY["Fraud Classification"]
        FC1[Pattern to fraud type: siphoned funds, duplicate claim, over-invoicing, ghost work]
    end

    subgraph LEGAL["Legal-Route Annotation"]
        LG1[HARDCODED lookup: fraud type to statute - BNS/PC Act/PMLA/RTI]
        LG2[Model NEVER outputs legal citations - locked rule]
    end

    subgraph EVID["Evidence Dossier Builder"]
        E1[Pulls raw rows from original Recommended/Sanctioned/Completed/Expenditure files as proof, not just the flag]
    end

    subgraph UI["Agency Dashboard"]
        U1[Investigation Queue - ranked by risk]
        U2[Case Drill-down + Timeline]
        U3[MP-risk view from Aggregate Table]
    end

    subgraph DEMO["Judging Setup"]
        DM1[Offline snapshot export - full pipeline output frozen, zero live API at demo time]
    end

    subgraph LOOP["Feedback Loop - locked selling point, shown as roadmap arrow"]
        G1[Agency confirms/rejects flag]
        G2[Confirmed rows become labeled training data]
        G3[Model retrains, weights update]
    end

    L1-->C1
    L2-->C1
    L3-->C1
    L4-->C1
    RS1-->C1
    RS2-->C1
    RS3-->C1
    RS4-->C1
    C1-->C2-->C3-->C4-->C5
    C5-->C5A
    C5-->C5B
    C5A-->M1
    C5B-->M1
    M1-->M2-->M3
    L5-->M3
    RS5-->M3
    L6-->M4
    M3-->M4-->M5-->O1
    M5-->O2
    M5-->O3
    O1-->A1-->A2
    O1-->F1
    O1-->F2
    O1-->F3
    O1-->F4
    F1-->D1
    F2-->D1
    F3-->D2
    F4-->D3
    D0-->D2
    D1-->FC1
    D2-->FC1
    D3-->FC1
    FC1-->LG1-->LG2
    FC1-->E1
    LG2-->U1
    E1-->U2
    A2-->U3
    U1-->DM1
    U1-.->G1-.->G2-.->G3-.->D1
```

**Source file:** `architecture/sih26102_full_architecture.mermaid`

---

## Model Plan — `paraphrase-multilingual-MiniLM-L12-v2` (fine-tune)

**Why this model (not `all-MiniLM-L6-v2`):** our raw data contains **romanized Hindi/regional text typed in English letters** — e.g. `Bhavan/Bhawan`, `Vistar`, `Samudayik`, `Shauchalaya`, `Kharanja`, `Nali Nirman`, plus village names like `Belavatagi`, `Chubba khola`. `all-MiniLM-L6-v2` is English-only and splits `Shauchalaya` into nonsense subwords, so `Bhavan` vs `Bhawan` vs `भवन` look unrelated. The multilingual model was trained on 50+ languages + parallel + code-mixed data, so it correctly maps romanized Hindi ↔ English → duplicate-work detection actually works.

**Size / speed:**
- `paraphrase-multilingual-MiniLM-L12-v2`: **118M params, 12 layers, 384-dim embeddings, ~420 MB on disk.**
- vs `all-MiniLM-L6-v2`: 22M params, 6 layers, ~80 MB — this one is ~5× larger but **same embedding size**, so the pipeline (vector DB, cosine search) is unchanged.
- On our 4 GB VRAM RTX 3050: ~40–60 ms/batch of 32 for encoding; fine-tuning fits with batch 8–16.

**Fine-tune approach:** contrastive/siamese training with `MultipleNegativesRankingLoss` or `CosineSimilarityLoss` on synthetic pairs built from real works (duplicate = positive, random = negative, hard negatives = same MP + same amount + different village). The frozen model already works for the demo — fine-tuning is a stretch goal.

**Hard rule (locked):** the model **NEVER outputs legal citations.** Legal route is appended by a hardcoded lookup table (BNS / PC Act / PMLA / RTI). Model only outputs fraud type + plain-language narrative.

---

## Data

| Source | Rows | Purpose |
|---|---|---|
| Works Recommended / Sanctioned / Completed | 39k / 31k / 34k | Work lifecycle (LS) |
| Expenditure | 30k | Disbursements (LS) |
| Lok Sabha allocation limits | 543 MPs | Denominator + MP budget cap |
| Calamity consent | 13 | Exceptions to allocation limits |
| **Master (built)** — `data/mplads_master_works_v3.csv` | **17,879 × 28** | Canonical table, both chambers, all-roster MPs even with zero works |

Known data quirks (preserved as flags, never silently dropped): `NA-` unparseable work-IDs, mixed romanized-Hindi titles, some column-shifted rows.

---

## Repo Layout

```
mplads/
├── data/                 # raw exports + master CSV (raw/ gitignored)
├── scripts/              # similarity demo, pair builder, fine-tune
├── architecture/         # .mermaid diagrams
├── notebooks/            # EDA / results graphs
├── models/               # trained checkpoints (gitignored — keep on disk/GDrive)
├── analysis/             # problem-statement deep dives
└── ps-2026/              # SIH problem statement source
```

**Trained models live in `models/`** — they are **not** committed to git (large binaries). The `.gitkeep` keeps the folder tracked; weights are re-downloadable or stored externally (e.g. Google Drive).

---

## Getting Started

```bash
# Python >= 3.10, ~4 GB VRAM GPU (or CPU — just slower)
git clone https://github.com/ZeroiJ/mplads.git
cd mplads
python -m venv .venv && source .venv/bin/activate
pip install sentence-transformers torch pandas scikit-learn

# Quick sanity demo: English-only vs multilingual on romanized Hindi titles
python scripts/similarity_demo.py
```

---

## Demo Scope (SIH judging)

- **30–60% MVP**: LS chamber end-to-end, offline snapshot export (zero live API at demo time).
- **Stretch**: RS chamber, fine-tuned model, feedback loop (agency confirmation → labeled data → retrain).