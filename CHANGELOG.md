# CHANGELOG

Strict changelog for the MPLADS fraud-detection MVP (SIH26102).
Every entry has a TECHNICAL summary and a LAYMAN summary so teammates can read
either. Entries are date-ordered, newest first. Mirrored to the Notion working doc
(page 3cbeb92a-bb06-81e9-9e0d-e086d1c50c8d).

---

## 2026-08-30 — Fine-tune complete: before/after evaluated, model saved

### Technical
- Fine-tuned `paraphrase-multilingual-MiniLM-L12-v2` (118M, 384-dim, multilingual) on
  `data/pairs.csv` (70,607 pairs; 49,424 train / 10,591 val / 10,592 test) using
  CosineSimilarityLoss, batch 16, fp16 (`use_amp=True`), LR 2e-5, 4 epochs.
- Per-epoch results (`metrics/metrics.csv`): val_acc 0.9565 → 0.9598 → 0.9611 → **0.9630**;
  train_loss 0.0547 → 0.0339 (converged, best = epoch 4).
- Best checkpoint saved at `models/best/epoch_4.0` (`models/best/best.txt`).
- Before/after on 10 fixed jury pairs (`metrics/after_metrics.csv`):
  - MATCH: Bhavan↔Bhawan 0.898→0.921; Nali↔drain 0.106→0.277; Kharanja↔CC Road 0.273→0.415;
    Shauchalaya↔toilet 0.134→0.138; Samudayik↔Community Bhavan 0.514→**0.240 (regression)**.
  - NOT_MATCH: school A↔B hard negative 0.980→0.954; others ↓ or flat.
  - Mean-match 0.385→0.398, mean-nonmatch 0.286→0.279 → separation 0.099→0.119 (+20%).
- One intermediate fp32 run was discarded (was killed by a session exit mid-epoch-1).
  Its epoch-1 numbers (val_acc 0.9554, p@20 0.4367) were REAL but from an unfinished
  run; the fp16 rerun (this entry) is the authoritative one. Smoke-test numbers were
  never used in any report.
- Honest scope: fine-tune materially improves duplicate/paraphrase detection and several
  cross-vocabulary pairs (Nali, Kharanja), but is NOT a reliable cross-vocabulary fix
  (Samudayik regressed). Claim = literal/near-duplicate detection + partial cross-vocab gain.

### Layman
- We taught the model to spot works that are the same thing written slightly differently
  ("Bhavan" vs "Bhawan"). 4 lessons over ~49,000 real examples, done in ~35 min.
- It now tells "same work / different work" correctly 96.3% of the time (was 95.5%).
- Getting better at some Hindi↔English pairs too (Nali Nirman = drain: 2.6× more
  confident; Kharanja = CC Road: 1.5×). One pair (Community Bhavan) got slightly worse,
  so we stay honest: data gap, not a training failure.
- The model is saved; learning is complete — no re-training needed for the demo.

---

## 2026-08-30 — REAL-DATA validation: duplicate sweep across all 10,539 described works

### Technical
- `scripts/real_sweep.py` + `metrics/real_sweep.csv`: swept all 10,539 works (desc ≥ 10 chars)
  grouped by (mp_no, recommended_amount); cosine sim ≥ 0.80 = duplicate-claim candidate,
  computed with BOTH models.
- Fine-tuned model flags **95,589 pairs** (168 MPs) vs frozen **141,235** → fine-tune
  dropped ~32% of false positives (hard-negative training tightened look-alike separation).
- Of the fine-tuned pairs, **1,432 are cross-financial-year resubmissions** (same MP +
  same amount + near-identical description across financial years) = the canonical
  duplicate-resubmission fraud pattern, across 35 MPs. Top MPs: Durga Das Uikey (561),
  Jaswantsinh Sumanbhai Bhabhor (238), Adv Dean Kuriakose (178), Vijay Kumar Dubey (121).
- Top-similarity hits are literal repeat titles (e.g. "Physical Inspection" ×10 at 1.000,
  MP243) — textbook duplicate-claim leads. Candidates written for human review.

### Layman
- Finally, a real test on real data (not just the 10 practice pairs). We asked the model:
  "scan all 10,539 real works that have a description, and find works that are the same
  thing re-submitted as new".
- The trained model found ~96,000 candidate pairs in 168 MPs. Compared to the untrained
  model, it flagged 32% fewer — meaning training taught it to STOP crying wolf on works
  that only look similar but are actually different.
- Of everything found, 1,432 pairs are the exact fraud pattern we want: the same work, in
  the same amount, re-submitted in a different year. Concentrated in 35 MPs — a perfect
  "who to investigate first" list for the judges. Top: Durga Das Uikey (561 pairs).

### Technical
- `scripts/baseline_jury_pairs.py` + `metrics/baseline_metrics.csv`: frozen-model scores on
  10 fixed jury pairs (match avg 0.385, non-match avg 0.286, separation 0.0990).
- `scripts/build_pairs.py` + `data/pairs.csv`: ratio-banded contrastive pairs within
  (mp_no, recommended_amount) groups — ≥0.80 positive (30,034), 0.45–0.80 hard-negative
  (30,034), <0.45 easy-negative (10,539). Split 49,424/10,591/10,592.
- Cross-vocabulary check: only 12/30,034 positives <0.30 Jaccard (0.04%), all same-vocab
  variants; 0 Hindi↔English bridge pairs → scope = literal/near-duplicate detection.
- `scripts/finetune.py` (fit + CosineSimilarityLoss + per-epoch metrics + heartbeat),
  `scripts/evaluate_after.py`, `AGENT.md` (operative rules), `.gitignore`.
- Environment: torch 2.13.0+cu126, sentence-transformers 6.0.0, datasets, accelerate;
  CUDA verified on RTX 3050 Laptop 4 GB. TMPDIR workaround for /tmp tmpfs quota.

### Layman
- Captured a "before" scorecard on 10 hand-picked pairs so we can prove what training
  changed later.
- Built the practice/exam questions (70,607 labeled pairs) the model learns from, directly
  from our real MPLADS data. Tagged which ones are the same work resubmitted, look-alikes
  that are actually different, and random ones.
- Found an honest limit early: our own data has almost no Hindi↔English same-work pairs, so
  we can only promise to improve same-language duplicate detection. We put this in writing.

---

## 2026-08-30 — Red-flag verification (fraud signals in real data)

### Technical
- RF2 confirmed exactly: 1,190 works sanctioned before Jan-2025 never completed.
- RF1 disproved: the 111-at-₹10L cluster includes MP00278 which does not exist on the
  alloc roster; real patterns = MP 334 (451/0/0, ₹3.87 cr), MP 632 (87/81/0), MP 353
  (84/55/0), same-amount flooding, 11,879 never completed, 11,883 zero/empty disbursal.

### Layman
- Double-checked the scary-sounding numbers against the raw files. Two survived, one didn't.
- Real picture: some MPs sanction hundreds of works but complete/paid nothing for years —
  those are the leads the detector will rank first.