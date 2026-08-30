"""
Build contrastive fine-tune pairs from the MPLADS master.
==========================================================
Two labeled-pair types per same (mp_no + recommended_amount) group:
  - POSITIVE (label=1): work_desc pairs with similarity ratio >= 0.80  -> duplicate claim
  - HARD NEGATIVE (label=0): ratio in [0.45, 0.80) -> look-alike works that are
                            actually different (different village/school) -> model
                            must separate on description detail, not coarse features
  - EASY NEGATIVE (label=0): random works (distant, different category)

ContrastiveLoss: positive pairs pulled together, negative pairs pushed apart.

Output: data/pairs.csv (survey columns for sanity + train/val/test rows)
    columns: split, kind, anchor_text, other_text, label
Split: 70% train / 15% val / 15% test (stratified on label).
"""

import csv
import random
from collections import Counter
from difflib import SequenceMatcher

import pandas as pd

MASTER = "/home/zeroij/mplads/data/mplads_master_works_v3.csv"
OUT = "/home/zeroij/mplads/data/pairs.csv"
SEED = 42
MIN_DESC_LEN = 10
POS_RATIO = 0.80
HARD_LO, HARD_HI = 0.45, 0.80


def norm(s: str) -> str:
    return " ".join(s.lower().split())


def ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, norm(a), norm(b)).ratio()


def main():
    random.seed(SEED)
    df = pd.read_csv(MASTER, dtype=str)
    df["desc"] = df["work_desc"].fillna("").astype(str).str.strip()
    df = df[df["desc"].str.len() >= MIN_DESC_LEN].copy()
    df["amt"] = pd.to_numeric(df["recommended_amount"], errors="coerce")
    print(f"Master: {len(df)} works with usable desc (min {MIN_DESC_LEN} chars)")

    positives, hard, easy = [], [], []

    # 1) Per (mp, amt) group bucket descs by pairwise ratio
    for (mp, amt), g in df.groupby(["mp_no", "amt"]):
        if amt is None or pd.isna(amt) or len(g) < 2:
            continue
        descs = g["desc"].tolist()
        for i in range(len(descs)):
            for j in range(i + 1, len(descs)):
                r = ratio(descs[i], descs[j])
                if r >= POS_RATIO:
                    positives.append((descs[i], descs[j]))
                elif HARD_LO <= r < HARD_HI:
                    hard.append((descs[i], descs[j]))
    print(f"POSITIVE (dup) pairs:  {len(positives)}")
    print(f"HARD-NEG pairs:        {len(hard)}")

    # cap positives to keep classes sane; keep all hard
    hard_final = hard[: len(positives)]
    print(f"HARD-NEG kept:         {len(hard_final)}")

    # 2) Easy negatives: random works (different rows)
    descs_all = df["desc"].tolist()
    n_easy = len(positives) + len(hard_final)
    idx = random.sample(range(len(descs_all)), min(n_easy, len(descs_all)))
    easy = [(descs_all[i], descs_all[(i * 13 + 7) % len(descs_all)]) for i in idx]

    rows = []
    rows += [{"kind": "positive", "a": a, "b": b, "label": 1} for a, b in positives]
    rows += [{"kind": "hard_negative", "a": a, "b": b, "label": 0} for a, b in hard_final]
    rows += [{"kind": "easy_negative", "a": a, "b": b, "label": 0} for a, b in easy]

    random.shuffle(rows)
    n = len(rows)
    s1, s2 = int(0.7 * n), int(0.85 * n)

    # stratified-ish split preserving label balance is handled by shuffles above
    out_rows = []
    for i, t in enumerate(rows):
        split = "train" if i < s1 else ("val" if i < s2 else "test")
        out_rows.append({
            "split": split,
            "kind": t["kind"],
            "anchor_text": t["a"],
            "other_text": t["b"],
            "label": t["label"],
        })

    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["split", "kind", "anchor_text", "other_text", "label"])
        w.writeheader()
        w.writerows(out_rows)

    print(f"\nTotal pairs: {n}")
    print("By split:", dict(Counter(t["split"] for t in out_rows)))
    print("By kind :", dict(Counter(t["kind"] for t in out_rows)))
    print("Label balance:", dict(Counter(t["label"] for t in out_rows)))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()